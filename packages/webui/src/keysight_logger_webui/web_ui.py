from __future__ import annotations

import argparse
from datetime import datetime
import importlib.metadata
import os
import subprocess
import threading
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Optional
from uuid import uuid4

try:
    from fastapi import Body, FastAPI, HTTPException
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel
except ImportError as exc:  # pragma: no cover - exercised only without web deps
    raise RuntimeError(
        'Web UI dependencies are not installed. Run: uv pip install -e ".[dev]" --link-mode=copy'
    ) from exc

from keysight_logger_core import (
    StartControlPlaneHandle,
    StartRequest,
    StartRunEvent,
    StartRunResult,
    build_start_plan,
    generate_buffer_overflow_warnings,
    get_default_instrument_profile,
    resolve_trigger_mode,
    run_start_session,
    validate_start_request,
)
from keysight_logger_core.constants import UTC_PLUS_8
from keysight_logger_core.instrument import VisaInstrument
from keysight_logger_core.measurement import (
    get_measurement_definition,
    registered_measurement_types,
)
from keysight_logger_core.models import TriggerEvent, TriggerSource
from keysight_logger_core.runner import StartRunnerDependencies
from keysight_logger_core.validation import (
    BUFFER_DRAIN_SIZE_RANGE,
    HW_TRIGGER_DELAY_S_RANGE,
    MAX_SAMPLES_RANGE,
    SAMPLE_COUNT_RANGE,
    SW_MIN_INTERVAL_MS_RANGE,
    SW_QUEUE_MAX_RANGE,
    TIMEOUT_MS_RANGE,
    TIMER_INTERVAL_S_RANGE,
    TRIGGER_COUNT_RANGE,
    TRIGGER_TIMEOUT_MS_RANGE,
)


TRIGGER_MODES = (
    "software",
    "external",
    "immediate",
    "immediate-custom",
    "software-custom",
    "external-custom",
)
PACKAGE_NAME = "keysight-logger-webui"
LIVE_SAMPLE_CAPACITY = 5000


class RunStartRequest(BaseModel):
    resource: str
    csv: Optional[str] = None
    simulate: bool = False
    timeout_ms: int = 5000
    trigger_timeout_ms: int = 10000
    sw_trigger_port: int = 8765
    sw_min_interval_ms: int = 0
    sw_queue_max: int = 0
    trigger_mode: Optional[str] = None
    max_samples: Optional[int] = None
    trigger_count: Optional[int] = None
    sample_count: Optional[int] = None
    timer_interval_s: Optional[float] = None
    buffer_drain_size: Optional[int] = None
    allow_buffer_overflow_risk: bool = False
    hw_trigger_slope: str = "neg"
    hw_trigger_delay_s: float = 0.0
    measurement: str = "current-dc"
    nplc: float = 1.0
    auto_zero: bool | str = "on"
    auto_range: bool = True
    measurement_range: Optional[float] = None
    current_range: Optional[float] = None
    dcv_input_impedance: str = "default"
    vm_comp_slope: Optional[str] = None
    ac_bandwidth_hz: Optional[float] = None
    current_terminal: Optional[int] = None


@dataclass
class _RunHandle:
    run_id: str
    resource: str
    csv_path: Path
    measurement: str
    trigger_mode: str
    control_plane: "_WebControlPlane"
    ready_event: threading.Event = field(default_factory=threading.Event)
    worker: threading.Thread | None = None
    state: str = "starting"
    latest_status: str = "starting"
    captured: int = 0
    errors: int = 0
    fatal_error: str | None = None
    cleanup_status: str | None = None
    result: StartRunResult | None = None
    warnings: list[str] = field(default_factory=list)
    cleanup_messages: list[str] = field(default_factory=list)
    recent_samples: list[dict[str, Any]] = field(default_factory=list)


class WebRunError(RuntimeError):
    status_code = 500


class RunAlreadyActive(WebRunError):
    status_code = 409


class RunValidationError(WebRunError):
    status_code = 422


class NoActiveRun(WebRunError):
    status_code = 409


class CsvFolderSelectionUnavailable(WebRunError):
    status_code = 503


CsvOpener = Callable[[Path], Any]
DirectorySelector = Callable[[], Path | str | None]


class _WebControlPlane:
    def __init__(self, ready_cb: Callable[[], None]) -> None:
        self._ready_cb = ready_cb
        self._router: Any | None = None
        self._stop_cb: Callable[[], None] | None = None
        self._queue_max = 0
        self._min_interval_ms = 0
        self._last_accepted_monotonic = 0.0
        self._lock = threading.Lock()
        self._closed = False

    def start(
        self,
        *,
        router: Any,
        port: int,  # noqa: ARG002
        min_interval_ms: int,
        queue_max: int,
        stop_cb: Callable[[], None],
        status_provider: Callable[[], dict[str, object]],  # noqa: ARG002
    ) -> StartControlPlaneHandle:
        with self._lock:
            self._router = router
            self._stop_cb = stop_cb
            self._queue_max = max(0, int(queue_max))
            self._min_interval_ms = max(0, int(min_interval_ms))
            self._closed = False
        self._ready_cb()
        return StartControlPlaneHandle(_stop_fn=self.close)

    def trigger(self, metadata: dict[str, Any] | None = None) -> tuple[bool, str]:
        with self._lock:
            if self._closed or self._router is None:
                return False, "run_not_ready"
            accepted, reason = self._try_accept_trigger_locked()
            if not accepted:
                return False, reason
            event_metadata = {
                str(key): str(value)
                for key, value in (metadata or {}).items()
                if value is not None
            }
            published = self._router.publish(
                TriggerEvent.new(TriggerSource.SOFTWARE, event_metadata)
            )
            if not published:
                return False, "queue_full"
            return True, ""

    def stop_run(self) -> None:
        with self._lock:
            router = self._router
            stop_cb = self._stop_cb
        if router is not None:
            router.publish(TriggerEvent.new(TriggerSource.SOFTWARE, {"control": "stop"}))
        if stop_cb is not None:
            stop_cb()

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._router = None
            self._stop_cb = None

    def _try_accept_trigger_locked(self) -> tuple[bool, str]:
        assert self._router is not None
        if self._queue_max > 0 and self._router.size() >= self._queue_max:
            return False, "queue_full"
        if self._min_interval_ms <= 0:
            return True, ""

        import time

        now = time.monotonic()
        elapsed_ms = (now - self._last_accepted_monotonic) * 1000.0
        if self._last_accepted_monotonic > 0 and elapsed_ms < self._min_interval_ms:
            return False, "rate_limited"
        self._last_accepted_monotonic = now
        return True, ""


class _WebRunEventSink:
    def __init__(self, manager: "WebRunManager") -> None:
        self._manager = manager

    def emit(self, event: StartRunEvent) -> None:
        self._manager._record_event(event)


class WebRunManager:
    def __init__(
        self,
        *,
        runner_dependencies: StartRunnerDependencies | None = None,
        csv_opener: CsvOpener | None = None,
        directory_selector: DirectorySelector | None = None,
    ) -> None:
        self._runner_dependencies = runner_dependencies
        self._csv_opener = csv_opener or _open_with_default_app
        self._directory_selector = directory_selector or _select_directory_with_dialog
        self._lock = threading.Lock()
        self._active: _RunHandle | None = None
        self._starting = False
        self._last_status = self._idle_status()

    def capabilities(self) -> dict[str, Any]:
        profile = get_default_instrument_profile()
        measurements = []
        registered = set(registered_measurement_types())
        for measurement_type in profile.supported_measurement_types:
            if measurement_type not in registered:
                continue
            definition = get_measurement_definition(measurement_type)
            options = profile.get_measurement_options(measurement_type)
            ac_bandwidth_hz_options = list(getattr(options, "ac_bandwidth_hz_options", ()))
            current_terminal_options = list(getattr(options, "current_terminal_options", ()))
            measurements.append(
                {
                    "name": definition.canonical_name,
                    "internal_type": definition.internal_type,
                    "unit": definition.unit,
                    "range_label": definition.range_label,
                    "range_options": [
                        {"label": label, "value": value}
                        for label, value in options.range_options
                    ],
                    "nplc_options": list(options.nplc_options),
                    "supports_nplc": bool(options.nplc_options),
                    "accepts_current_range_alias": definition.accepts_current_range_alias,
                    "ac_bandwidth_hz_options": ac_bandwidth_hz_options,
                    "current_terminal_options": current_terminal_options,
                    "supports_ac_bandwidth": bool(ac_bandwidth_hz_options),
                    "supports_current_terminal": bool(current_terminal_options),
                }
            )
        return {
            "instrument_profile": {
                "vendor": profile.vendor,
                "model": profile.model,
                "reading_memory_limit": profile.reading_memory_limit,
                "supports_buffered_reading_memory": profile.supports_buffered_reading_memory,
                "supports_bus_trigger": profile.supports_bus_trigger,
                "supports_external_trigger": profile.supports_external_trigger,
                "supports_sample_timer": profile.supports_sample_timer,
            },
            "measurements": measurements,
            "trigger_modes": list(TRIGGER_MODES),
            "limits": {
                "timeout_ms": _range_limit(TIMEOUT_MS_RANGE),
                "trigger_timeout_ms": _range_limit(TRIGGER_TIMEOUT_MS_RANGE),
                "max_samples": _range_limit(MAX_SAMPLES_RANGE),
                "trigger_count": _range_limit(TRIGGER_COUNT_RANGE),
                "sample_count": _range_limit(SAMPLE_COUNT_RANGE),
                "timer_interval_s": _range_limit(TIMER_INTERVAL_S_RANGE),
                "buffer_drain_size": _range_limit(BUFFER_DRAIN_SIZE_RANGE),
                "hw_trigger_delay_s": _range_limit(HW_TRIGGER_DELAY_S_RANGE),
                "sw_min_interval_ms": {
                    **_range_limit(SW_MIN_INTERVAL_MS_RANGE),
                    "nonzero_min": 50,
                },
                "sw_queue_max": _range_limit(SW_QUEUE_MAX_RANGE),
            },
            "defaults": {
                "measurement": "current-dc",
                "trigger_mode": "software",
                "timeout_ms": 5000,
                "trigger_timeout_ms": 10000,
                "nplc": 1.0,
                "auto_zero": "on",
                "auto_range": True,
                "dcv_input_impedance": "default",
                "hw_trigger_slope": "neg",
                "hw_trigger_delay_s": 0.0,
                "ac_bandwidth_hz": None,
                "current_terminal": None,
            },
        }

    def list_resources(self, verify: bool = False, live_only: bool = False) -> dict[str, Any]:
        effective_verify = bool(verify or live_only)
        resources: list[dict[str, Any]] = []
        for resource in VisaInstrument.list_resources():
            if not effective_verify:
                resources.append({"resource": resource})
                continue
            live, detail = VisaInstrument.verify_resource(resource)
            if live_only and not live:
                continue
            resources.append(
                {
                    "resource": resource,
                    "live": live,
                    "status": "live" if live else "stale",
                    "detail": detail,
                }
            )
        return {
            "resources": resources,
            "verify": effective_verify,
            "live_only": bool(live_only),
        }

    def start(self, request: RunStartRequest) -> dict[str, Any]:
        with self._lock:
            if self._starting or (
                self._active is not None and self._is_handle_active(self._active)
            ):
                raise RunAlreadyActive("a run is already active")
            self._starting = True

        handle: _RunHandle | None = None
        try:
            start_request = self._validate_request(request)
            profile = get_default_instrument_profile()
            trigger_mode = resolve_trigger_mode(start_request)
            warnings = generate_buffer_overflow_warnings(start_request, trigger_mode, profile)
            plan = build_start_plan(
                start_request,
                trigger_mode,
                profile,
                buffer_warnings=warnings,
            )
            runtime_request = replace(start_request, csv=plan.csv_path)
            run_id = str(uuid4())
            control_plane = _WebControlPlane(lambda: self._mark_handle_ready(run_id))
            handle = _RunHandle(
                run_id=run_id,
                resource=runtime_request.resource,
                csv_path=Path(plan.csv_path),
                measurement=plan.measurement_name,
                trigger_mode=trigger_mode,
                control_plane=control_plane,
                warnings=warnings,
            )
            worker = threading.Thread(
                target=self._run_worker,
                args=(handle, runtime_request, profile),
                name=f"keysight-web-run-{run_id}",
                daemon=True,
            )
            handle.worker = worker
            with self._lock:
                self._active = handle
                self._last_status = self._status_from_handle(handle)
            worker.start()
            handle.ready_event.wait(timeout=max(runtime_request.timeout_ms / 1000.0 + 1.0, 2.0))
            status = self.status()
            with self._lock:
                self._starting = False
                result = handle.result
                if result is not None and not result.ok and result.reason == "connect_error":
                    self._active = None
                    self._last_status = status
                    raise RuntimeError(result.fatal_error or "connect_error")
            return status
        except ValueError as exc:
            with self._lock:
                self._starting = False
                if handle is not None and self._active is handle:
                    self._active = None
            raise RunValidationError(str(exc)) from exc
        except Exception:
            with self._lock:
                self._starting = False
                if handle is not None and self._active is handle and not self._is_handle_active(handle):
                    self._active = None
            raise

    def status(self) -> dict[str, Any]:
        with self._lock:
            if self._active is None:
                return dict(self._last_status)
            status = self._status_from_handle(self._active)
            self._last_status = status
            return dict(status)

    def trigger(self, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            handle = self._active
            if handle is None or not self._is_handle_active(handle):
                raise NoActiveRun("no active run")
        accepted, reason = handle.control_plane.trigger(metadata)
        if not accepted:
            raise RunValidationError(reason)
        with self._lock:
            handle.latest_status = "software trigger queued"
            self._last_status = self._status_from_handle(handle)
            return dict(self._last_status)

    def stop(self) -> dict[str, Any]:
        with self._lock:
            handle = self._active
            if handle is None:
                return dict(self._last_status)
            if self._is_handle_active(handle):
                handle.state = "stopping"
                handle.latest_status = "stop requested"
                control_plane = handle.control_plane
            else:
                self._last_status = self._status_from_handle(handle)
                return dict(self._last_status)
        control_plane.stop_run()
        with self._lock:
            self._last_status = self._status_from_handle(handle)
            return dict(self._last_status)

    def open_current_csv(self) -> dict[str, Any]:
        status = self.status()
        if status.get("active"):
            raise RunAlreadyActive("run is still active")
        csv_path_text = status.get("csv_path")
        if not csv_path_text:
            raise NoActiveRun("no completed CSV available")
        csv_path = Path(csv_path_text)
        if not csv_path.exists():
            raise FileNotFoundError("CSV file not found")
        self._csv_opener(csv_path)
        return {"opened": True, "csv_path": str(csv_path)}

    def select_csv_folder(self) -> dict[str, Any]:
        try:
            selected = self._directory_selector()
        except CsvFolderSelectionUnavailable:
            raise
        except Exception as exc:
            raise CsvFolderSelectionUnavailable(str(exc) or "folder selection unavailable") from exc

        if selected is None or not str(selected).strip():
            return {"selected": False, "folder_path": None, "csv_path": None}

        folder_path = Path(str(selected))
        csv_path = folder_path / f"{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}.csv"
        return {
            "selected": True,
            "folder_path": str(folder_path),
            "csv_path": str(csv_path),
        }

    def _validate_request(self, request: RunStartRequest) -> StartRequest:
        raw = _model_dict(request)
        raw["resource"] = str(raw["resource"]).strip()
        if not raw["resource"]:
            raise RunValidationError("resource is required")
        if raw.get("csv") is not None:
            raw["csv"] = str(raw["csv"]).strip() or None
        if raw.get("trigger_mode") is not None:
            raw["trigger_mode"] = str(raw["trigger_mode"]).strip().lower()
            if raw["trigger_mode"] not in TRIGGER_MODES:
                raise RunValidationError(
                    "trigger_mode must be software, external, immediate, "
                    "immediate-custom, software-custom, or external-custom"
                )
        raw["hw_trigger_slope"] = str(raw["hw_trigger_slope"]).strip().lower()
        if raw["hw_trigger_slope"] not in {"pos", "neg"}:
            raise RunValidationError("hw_trigger_slope must be 'pos' or 'neg'")
        if raw.get("vm_comp_slope") is not None:
            raw["vm_comp_slope"] = str(raw["vm_comp_slope"]).strip().lower() or None
            if raw["vm_comp_slope"] is not None and raw["vm_comp_slope"] not in {"pos", "neg"}:
                raise RunValidationError("vm_comp_slope must be 'pos' or 'neg'")
        raw["dcv_input_impedance"] = _parse_dcv_input_impedance(raw["dcv_input_impedance"])

        # Normalize legacy boolean payloads while keeping Core's semantic strings.
        auto_zero_val = raw.get("auto_zero")
        if isinstance(auto_zero_val, bool):
            raw["auto_zero"] = "on" if auto_zero_val else "off"
        elif isinstance(auto_zero_val, str):
            normalized_val = auto_zero_val.strip().lower()
            if normalized_val in ("true", "on"):
                raw["auto_zero"] = "on"
            elif normalized_val in ("false", "off"):
                raw["auto_zero"] = "off"
            elif normalized_val == "once":
                raw["auto_zero"] = "once"
            else:
                raise RunValidationError(
                    "auto_zero must be 'on', 'off', 'once', or a boolean"
                )
        else:
            raw["auto_zero"] = "on"

        start_request = StartRequest(**raw)
        trigger_mode = resolve_trigger_mode(start_request)
        validate_start_request(
            start_request,
            trigger_mode,
            instrument_profile=get_default_instrument_profile(),
        )
        return start_request

    def _run_worker(
        self,
        handle: _RunHandle,
        request: StartRequest,
        profile: Any,
    ) -> None:
        result: StartRunResult | None = None
        try:
            result = run_start_session(
                request,
                handle.trigger_mode,
                profile,
                _WebRunEventSink(self),
                controls=None,
                control_plane=handle.control_plane,
                run_id=handle.run_id,
                dependencies=self._runner_dependencies,
            )
            with self._lock:
                handle.result = result
                handle.captured = result.captured
                handle.errors = result.errors
                handle.fatal_error = result.fatal_error
                handle.state = "stopped" if result.ok else "error"
                if result.ok:
                    handle.latest_status = "recording stopped"
                elif result.fatal_error:
                    handle.latest_status = result.fatal_error
                else:
                    handle.latest_status = result.reason
                self._last_status = self._status_from_handle(handle)
        except Exception as exc:  # pragma: no cover - defensive runtime boundary
            with self._lock:
                handle.fatal_error = f"{type(exc).__name__}: {exc}"
                handle.latest_status = handle.fatal_error
                handle.state = "error"
                self._last_status = self._status_from_handle(handle)
        finally:
            handle.ready_event.set()

    def _record_event(self, event: StartRunEvent) -> None:
        with self._lock:
            handle = self._active
            if handle is None or event.run_id != handle.run_id:
                return
            if event.event in {"message", "status", "error"} and event.message:
                handle.latest_status = event.message
            if event.event == "sample":
                handle.captured = int(event.captured or handle.captured)
                sample_payload = _sample_payload(event.sample, handle.captured)
                if sample_payload is not None:
                    handle.recent_samples.append(sample_payload)
                    del handle.recent_samples[:-LIVE_SAMPLE_CAPACITY]
            if event.event == "summary":
                handle.captured = int(event.captured or 0)
                handle.errors = int(event.errors or 0)
                handle.fatal_error = event.fatal_error
            if event.event == "error":
                handle.fatal_error = event.message
                handle.state = "error"
            if event.event == "message" and event.message:
                self._record_cleanup_message(handle, event.message)
            self._last_status = self._status_from_handle(handle)

    def _record_cleanup_message(self, handle: _RunHandle, message: str) -> None:
        cleanup_prefixes = (
            "main cleanup",
            "final cleanup",
            "waiting for measurement worker",
            "waiting worker",
            "release_to_local",
            "cleanup_release_to_local",
            "stopping software trigger server",
            "software trigger server stopped",
        )
        if not message.startswith(cleanup_prefixes):
            return
        handle.cleanup_messages.append(message)
        handle.cleanup_status = "; ".join(handle.cleanup_messages)

    def _mark_handle_ready(self, run_id: str) -> None:
        with self._lock:
            if self._active is None or self._active.run_id != run_id:
                return
            if self._active.state == "starting":
                self._active.state = "running"
            self._active.latest_status = "ready"
            self._active.ready_event.set()
            self._last_status = self._status_from_handle(self._active)

    def _status_from_handle(self, handle: _RunHandle) -> dict[str, Any]:
        active = self._is_handle_active(handle)
        state = handle.state
        if state in {"starting", "running", "stopping"} and not active:
            state = "error" if handle.fatal_error else "stopped"
        recent_samples = [dict(sample) for sample in handle.recent_samples]
        return {
            "run_id": handle.run_id,
            "state": state,
            "active": active,
            "resource": handle.resource,
            "measurement": handle.measurement,
            "trigger_mode": handle.trigger_mode,
            "csv_path": str(handle.csv_path),
            "captured": handle.captured,
            "errors": handle.errors,
            "latest_status": handle.latest_status,
            "fatal_error": handle.fatal_error,
            "cleanup_status": handle.cleanup_status,
            "warnings": list(handle.warnings),
            "latest_sample": dict(recent_samples[-1]) if recent_samples else None,
            "recent_samples": recent_samples,
            "sample_capacity": LIVE_SAMPLE_CAPACITY,
        }

    def _is_handle_active(self, handle: _RunHandle) -> bool:
        if handle.worker is None:
            return handle.state in {"starting", "running", "stopping"}
        return handle.worker.is_alive()

    @staticmethod
    def _idle_status() -> dict[str, Any]:
        return {
            "run_id": None,
            "state": "idle",
            "active": False,
            "resource": None,
            "measurement": None,
            "trigger_mode": None,
            "csv_path": None,
            "captured": 0,
            "errors": 0,
            "latest_status": "idle",
            "fatal_error": None,
            "cleanup_status": None,
            "warnings": [],
            "latest_sample": None,
            "recent_samples": [],
            "sample_capacity": LIVE_SAMPLE_CAPACITY,
        }


def create_app(manager: WebRunManager | None = None) -> FastAPI:
    static_dir = Path(__file__).with_name("static")
    app = FastAPI(title="Keysight Logger Web UI")
    app.state.manager = manager or WebRunManager()
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    @app.get("/api/capabilities")
    def api_capabilities() -> dict[str, Any]:
        return app.state.manager.capabilities()

    @app.get("/api/resources")
    def api_resources(verify: bool = False, live_only: bool = False) -> dict[str, Any]:
        try:
            return app.state.manager.list_resources(verify=verify, live_only=live_only)
        except Exception as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/api/runs")
    def api_start_run(payload: RunStartRequest) -> dict[str, Any]:
        try:
            return app.state.manager.start(payload)
        except WebRunError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/runs/current")
    def api_current_run() -> dict[str, Any]:
        return app.state.manager.status()

    @app.post("/api/runs/current/trigger", status_code=202)
    def api_trigger(payload: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
        try:
            return app.state.manager.trigger(payload)
        except WebRunError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    @app.post("/api/runs/current/stop", status_code=202)
    def api_stop() -> dict[str, Any]:
        return app.state.manager.stop()

    @app.post("/api/runs/current/open-csv")
    def api_open_csv() -> dict[str, Any]:
        try:
            return app.state.manager.open_current_csv()
        except WebRunError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/csv/select-folder")
    def api_select_csv_folder() -> dict[str, Any]:
        try:
            return app.state.manager.select_csv_folder()
        except WebRunError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    return app


def get_webui_version() -> str:
    try:
        return importlib.metadata.version(PACKAGE_NAME)
    except importlib.metadata.PackageNotFoundError:
        return _read_project_version()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="keysight-logger-webui")
    parser.add_argument("--version", action="version", version=f"%(prog)s {get_webui_version()}")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8767)
    args = parser.parse_args(argv)

    import uvicorn

    uvicorn.run(create_app(), host=args.host, port=args.port)
    return 0


def _model_dict(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _sample_payload(sample: Any, sequence: int) -> dict[str, Any] | None:
    if sample is None:
        return None
    timestamp_utc = getattr(sample, "timestamp_utc", None)
    if hasattr(timestamp_utc, "astimezone"):
        timestamp_text = timestamp_utc.astimezone(UTC_PLUS_8).isoformat()
    elif timestamp_utc is None:
        timestamp_text = None
    else:
        timestamp_text = str(timestamp_utc)
    return {
        "sequence": sequence,
        "timestamp_utc_plus_8": timestamp_text,
        "measurement_type": getattr(sample, "measurement_type", None),
        "value": getattr(sample, "value", None),
        "unit": getattr(sample, "unit", None),
        "trigger_id": getattr(sample, "trigger_id", None),
        "trigger_source": getattr(sample, "trigger_source", None),
        "trigger_metadata": _json_safe_mapping(
            getattr(sample, "trigger_metadata", {})
        ),
        "measurement_metadata": _json_safe_mapping(
            getattr(sample, "measurement_metadata", {})
        ),
        "resource_id": getattr(sample, "resource_id", None),
        "status": getattr(sample, "status", None),
    }


def _json_safe_mapping(value: Any) -> dict[str, Any]:
    safe_value = _json_safe_value(value or {})
    if isinstance(safe_value, dict):
        return safe_value
    return {}


def _json_safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe_value(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _read_project_version() -> str:
    pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
    try:
        import tomllib
    except ModuleNotFoundError:
        tomllib = None
    if tomllib is not None:
        with pyproject_path.open("rb") as fh:
            data = tomllib.load(fh)
        return str(data["project"]["version"])

    in_project = False
    for raw_line in pyproject_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            in_project = line == "[project]"
            continue
        if in_project and line.startswith("version") and "=" in line:
            return line.split("=", 1)[1].strip().strip('"')
    raise RuntimeError(f"Could not read project version from {pyproject_path}")


def _range_limit(value_range: tuple[float, float] | tuple[int, int]) -> dict[str, float | int]:
    return {"min": value_range[0], "max": value_range[1]}


def _parse_dcv_input_impedance(value: str) -> str:
    normalized = str(value).strip().lower()
    if normalized in {"default", "10m", "auto"}:
        return normalized
    raise RunValidationError("dcv_input_impedance must be 'default', '10m', or 'auto'")


def _open_with_default_app(path: Path) -> None:
    os.startfile(path)  # type: ignore[attr-defined]


def _select_directory_with_dialog() -> Path | None:
    script = (
        "$shell = New-Object -ComObject Shell.Application; "
        "$folder = $shell.BrowseForFolder(0, 'Select CSV output folder', 0); "
        "if ($folder -ne $null) { [Console]::Out.Write($folder.Self.Path) }"
    )
    try:
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-STA", "-Command", script],
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception as exc:  # pragma: no cover - platform/runtime dependent
        raise CsvFolderSelectionUnavailable("folder selection dialog is unavailable") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or "folder selection dialog is unavailable"
        raise CsvFolderSelectionUnavailable(detail)

    selected = completed.stdout.strip()
    return Path(selected) if selected else None


app = create_app()


if __name__ == "__main__":
    raise SystemExit(main())
