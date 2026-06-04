from __future__ import annotations

import argparse
import os
import threading
import time
from dataclasses import dataclass
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
        "Web UI dependencies are not installed. Run: pip install -r requirements.txt"
    ) from exc

from .acquisition import TriggerAcquisitionEngine
from .cli import (
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
    parse_dcv_input_impedance,
    resolve_csv_path,
    resolve_measurement_range,
    resolve_trigger_mode,
    validate_start_args,
)
from .instrument import InstrumentConfig, VisaInstrument
from .measurement import (
    create_measurement_plugin,
    format_measurement_type,
    get_measurement_definition,
    normalize_measurement_type,
    registered_measurement_types,
)
from .models import AcquisitionConfig, TriggerEvent, TriggerSource, get_default_instrument_profile
from .storage import CsvWriter
from .trigger import TriggerRouter


TRIGGER_MODES = (
    "software",
    "external",
    "immediate",
    "immediate-custom",
    "software-custom",
    "external-custom",
)


class RunStartRequest(BaseModel):
    resource: str
    csv: Optional[str] = None
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
    enable_hw_trigger: bool = False
    hw_trigger_slope: str = "neg"
    hw_trigger_delay_s: float = 0.0
    measurement: str = "current-dc"
    nplc: float = 1.0
    auto_zero: bool = True
    auto_range: bool = True
    measurement_range: Optional[float] = None
    current_range: Optional[float] = None
    dcv_input_impedance: str = "default"
    vm_comp_slope: Optional[str] = None


@dataclass
class _RunHandle:
    run_id: str
    resource: str
    csv_path: Path
    measurement: str
    trigger_mode: str
    hardware_trigger_slope: str
    router: TriggerRouter
    engine: TriggerAcquisitionEngine
    instrument: VisaInstrument
    min_interval_ms: int
    queue_max: int
    worker: threading.Thread | None = None
    state: str = "starting"
    latest_status: str = "starting"
    fatal_error: str | None = None
    cleanup_status: str | None = None
    last_accepted_monotonic: float = 0.0


class WebRunError(RuntimeError):
    status_code = 500


class RunAlreadyActive(WebRunError):
    status_code = 409


class RunValidationError(WebRunError):
    status_code = 422


class NoActiveRun(WebRunError):
    status_code = 409


InstrumentFactory = Callable[[InstrumentConfig], VisaInstrument]
StorageFactory = Callable[[Path], CsvWriter]
CsvOpener = Callable[[Path], Any]


class WebRunManager:
    def __init__(
        self,
        instrument_factory: InstrumentFactory = VisaInstrument,
        measurement_factory: Callable[[str], Any] = create_measurement_plugin,
        storage_factory: StorageFactory = CsvWriter,
        csv_opener: CsvOpener | None = None,
    ) -> None:
        self._instrument_factory = instrument_factory
        self._measurement_factory = measurement_factory
        self._storage_factory = storage_factory
        self._csv_opener = csv_opener or _open_with_default_app
        self._lock = threading.Lock()
        self._active: _RunHandle | None = None
        self._starting = False
        self._last_status = self._idle_status()

    def capabilities(self) -> dict[str, Any]:
        profile = get_default_instrument_profile()
        measurements = []
        for measurement_type in profile.supported_measurement_types:
            if measurement_type not in registered_measurement_types():
                continue
            definition = get_measurement_definition(measurement_type)
            options = profile.get_measurement_options(measurement_type)
            measurements.append(
                {
                    "name": definition.cli_name,
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
                "auto_zero": True,
                "auto_range": True,
                "dcv_input_impedance": "default",
                "hw_trigger_slope": "neg",
                "hw_trigger_delay_s": 0.0,
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
        args = self._validate_request(request)
        with self._lock:
            if self._starting or (
                self._active is not None and self._is_handle_active(self._active)
            ):
                raise RunAlreadyActive("a run is already active")
            self._starting = True

        trigger_mode = resolve_trigger_mode(args)
        measurement_type = normalize_measurement_type(args.measurement)
        measurement_range = resolve_measurement_range(args)
        csv_path = resolve_csv_path(args.csv)

        try:
            instrument = self._instrument_factory(
                InstrumentConfig(resource_string=args.resource, timeout_ms=args.timeout_ms)
            )
        except Exception:
            with self._lock:
                self._starting = False
            raise
        try:
            instrument.connect()
        except Exception:
            try:
                instrument.close()
            except Exception:
                pass
            with self._lock:
                self._starting = False
            raise

        try:
            run_id = str(uuid4())
            router = TriggerRouter()
            storage = self._storage_factory(csv_path)
            measurement = self._measurement_factory(measurement_type)

            config = AcquisitionConfig(
                measurement_type=measurement_type,
                trigger_timeout_ms=args.trigger_timeout_ms,
                max_samples=args.max_samples,
                trigger_count=args.trigger_count,
                sample_count=args.sample_count,
                timer_interval_s=args.timer_interval_s,
                buffer_drain_size=args.buffer_drain_size,
                allow_buffer_overflow_risk=args.allow_buffer_overflow_risk,
                nplc=args.nplc,
                auto_zero=args.auto_zero,
                auto_range=args.auto_range,
                measurement_range=measurement_range,
                current_range=args.current_range,
                dcv_input_impedance=args.dcv_input_impedance,
                hw_trigger_delay_s=args.hw_trigger_delay_s,
                vm_comp_slope=args.vm_comp_slope,
            )
            engine = TriggerAcquisitionEngine(
                instrument=instrument,
                measurement=measurement,
                storage=storage,
                config=config,
                router=router,
                status_cb=lambda message: self._record_status(run_id, message),
                instrument_profile=get_default_instrument_profile(),
            )
            handle = _RunHandle(
                run_id=run_id,
                resource=args.resource,
                csv_path=csv_path,
                measurement=format_measurement_type(measurement_type),
                trigger_mode=trigger_mode,
                hardware_trigger_slope=args.hw_trigger_slope,
                router=router,
                engine=engine,
                instrument=instrument,
                min_interval_ms=args.sw_min_interval_ms,
                queue_max=args.sw_queue_max,
            )
            worker = threading.Thread(
                target=self._run_worker,
                args=(handle,),
                name=f"keysight-web-run-{run_id}",
                daemon=True,
            )
            handle.worker = worker
        except Exception:
            with self._lock:
                self._starting = False
            try:
                instrument.close()
            except Exception:
                pass
            raise
        with self._lock:
            self._active = handle
            self._starting = False
            self._last_status = self._status_from_handle(handle)
        try:
            worker.start()
        except Exception:
            with self._lock:
                if self._active is handle:
                    self._active = None
                self._starting = False
                self._last_status = self._idle_status()
            try:
                instrument.close()
            except Exception:
                pass
            raise
        return self.status()

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
            accepted, reason = self._try_accept_trigger(handle)
            if not accepted:
                raise RunValidationError(reason)
            event_metadata = {
                str(key): str(value)
                for key, value in (metadata or {}).items()
                if value is not None
            }
            handle.router.publish(TriggerEvent.new(TriggerSource.SOFTWARE, event_metadata))
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
                handle.engine.stop()
                handle.router.publish(
                    TriggerEvent.new(TriggerSource.SOFTWARE, {"control": "stop"})
                )
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

    def _validate_request(self, request: RunStartRequest) -> argparse.Namespace:
        args = argparse.Namespace(**_model_dict(request))
        args.resource = str(args.resource).strip()
        if not args.resource:
            raise RunValidationError("resource is required")
        if args.trigger_mode is not None:
            args.trigger_mode = str(args.trigger_mode).strip().lower()
            if args.trigger_mode not in TRIGGER_MODES:
                raise RunValidationError(
                    "trigger_mode must be software, external, immediate, "
                    "immediate-custom, software-custom, or external-custom"
                )
        args.hw_trigger_slope = str(args.hw_trigger_slope).strip().lower()
        if args.hw_trigger_slope not in {"pos", "neg"}:
            raise RunValidationError("hw_trigger_slope must be 'pos' or 'neg'")
        if args.vm_comp_slope is not None:
            args.vm_comp_slope = str(args.vm_comp_slope).strip().lower()
            if args.vm_comp_slope not in {"pos", "neg"}:
                raise RunValidationError("vm_comp_slope must be 'pos' or 'neg'")
        try:
            args.dcv_input_impedance = parse_dcv_input_impedance(args.dcv_input_impedance)
            trigger_mode = resolve_trigger_mode(args)
            validate_start_args(args, trigger_mode, instrument_profile=get_default_instrument_profile())
        except (ValueError, argparse.ArgumentTypeError) as exc:
            raise RunValidationError(str(exc)) from exc
        return args

    def _run_worker(self, handle: _RunHandle) -> None:
        fatal_error = None
        try:
            with self._lock:
                handle.state = "running"
                self._last_status = self._status_from_handle(handle)
            handle.engine.run(
                trigger_mode=handle.trigger_mode,
                hardware_trigger_slope=handle.hardware_trigger_slope,
            )
            fatal_error = handle.engine.fatal_error
        except Exception as exc:  # pragma: no cover - covered through API status behavior
            fatal_error = f"{type(exc).__name__}: {exc}"
        finally:
            cleanup_parts: list[str] = []
            try:
                cleanup_parts.append(f"release_to_local: {handle.instrument.release_to_local()}")
            except Exception as exc:
                cleanup_parts.append(f"release_to_local failed: {type(exc).__name__}: {exc}")
            try:
                handle.instrument.close()
                cleanup_parts.append("close: ok")
            except Exception as exc:
                cleanup_parts.append(f"close failed: {type(exc).__name__}: {exc}")
            try:
                cleanup_parts.append(
                    f"cleanup_release_to_local: {handle.instrument.cleanup_release_to_local()}"
                )
            except Exception as exc:
                cleanup_parts.append(
                    f"cleanup_release_to_local failed: {type(exc).__name__}: {exc}"
                )
            with self._lock:
                handle.cleanup_status = "; ".join(cleanup_parts)
                handle.fatal_error = fatal_error
                if fatal_error:
                    handle.state = "error"
                    handle.latest_status = fatal_error
                else:
                    handle.state = "stopped"
                    if handle.latest_status not in {"stop requested", "software trigger queued"}:
                        handle.latest_status = "recording stopped"
                self._last_status = self._status_from_handle(handle)

    def _record_status(self, run_id: str, message: str) -> None:
        with self._lock:
            if self._active is None or self._active.run_id != run_id:
                return
            self._active.latest_status = message
            self._last_status = self._status_from_handle(self._active)

    def _try_accept_trigger(self, handle: _RunHandle) -> tuple[bool, str]:
        if handle.queue_max > 0 and handle.router.size() >= handle.queue_max:
            return False, "queue_full"
        if handle.min_interval_ms <= 0:
            return True, ""
        now = time.monotonic()
        elapsed_ms = (now - handle.last_accepted_monotonic) * 1000.0
        if handle.last_accepted_monotonic > 0 and elapsed_ms < handle.min_interval_ms:
            return False, "rate_limited"
        handle.last_accepted_monotonic = now
        return True, ""

    def _status_from_handle(self, handle: _RunHandle) -> dict[str, Any]:
        worker_alive = handle.worker.is_alive() if handle.worker is not None else False
        state = handle.state
        if state in {"starting", "running"} and not worker_alive:
            state = "error" if handle.fatal_error or handle.engine.fatal_error else "stopped"
        return {
            "run_id": handle.run_id,
            "state": state,
            "active": self._is_handle_active(handle),
            "resource": handle.resource,
            "measurement": handle.measurement,
            "trigger_mode": handle.trigger_mode,
            "csv_path": str(handle.csv_path),
            "captured": handle.engine.stats.captured,
            "errors": handle.engine.stats.errors,
            "latest_status": handle.latest_status,
            "fatal_error": handle.fatal_error or handle.engine.fatal_error,
            "cleanup_status": handle.cleanup_status,
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

    return app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m keysight_logger.web_ui")
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


def _range_limit(value_range: tuple[float, float] | tuple[int, int]) -> dict[str, float | int]:
    return {"min": value_range[0], "max": value_range[1]}


def _open_with_default_app(path: Path) -> None:
    os.startfile(path)  # type: ignore[attr-defined]


app = create_app()


if __name__ == "__main__":
    raise SystemExit(main())
