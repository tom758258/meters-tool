from __future__ import annotations

from collections import deque
from datetime import datetime
import json
import threading
import time
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Iterator, Literal, Optional
from uuid import uuid4

try:
    from pydantic import BaseModel
except ImportError as exc:  # pragma: no cover - exercised only without web deps
    raise RuntimeError(
        'Web UI dependencies are not installed. Run: uv pip install -e ".[webui]" --link-mode=copy'
    ) from exc

from meters_tool_core import (
    StartControlPlaneHandle,
    StartRequest,
    StartRunEvent,
    StartRunResult,
    build_start_plan,
    generate_buffer_overflow_warnings,
    resolve_instrument_profile,
    resolve_trigger_mode,
    run_start_session,
    validate_start_request,
    validate_start_workflow_support,
)
from meters_tool_core._version import (
    DISTRIBUTION_NAME,
    FALLBACK_PACKAGE_VERSION,
    get_distribution_version,
)
from meters_tool_core.command import SoftwareTriggerCommand
from meters_tool_core.instrument import InstrumentError, VisaInstrument
from meters_tool_core.models import (
    Transport,
    TriggerEvent,
    TriggerSource,
    find_instrument_profile_by_idn,
)
from meters_tool_core.runner import StartRunnerDependencies
from meters_tool_core.start_resolution import resolve_start_profile
from meters_tool_webui._run_request import normalize_run_request_values
from meters_tool_webui._web_payloads import (
    build_capabilities_payload,
    resource_model_metadata,
    sample_payload,
)


PACKAGE_NAME = "meters-tool-webui"
FALLBACK_WEBUI_VERSION = FALLBACK_PACKAGE_VERSION
LIVE_SAMPLE_CAPACITY = 5000
SSE_EVENT_NAME = "run-status"
SSE_KEEPALIVE_INTERVAL_S = 5.0


class RunStartRequest(BaseModel):
    resource: str
    visa_library: Literal["", "@py"] | None = None
    instrument_model: Optional[str] = None
    csv: Optional[str] = None
    csv_enabled: bool = True
    csv_format: Literal["full", "data"] = "data"
    csv_time_columns: tuple[Literal["elapsed", "delta"], ...] = ()
    simulate: bool = False
    timeout_ms: int = 5000
    trigger_timeout_ms: int = 10000
    sw_trigger_port: int = 8765
    sw_min_interval_ms: int = 0
    sw_queue_max: int = 0
    trigger_mode: Optional[str] = None
    max_samples: Optional[int] = None
    trigger_count: Optional[int] = None
    trigger_count_infinite: bool = False
    monitor_overflow: bool = False
    stop_on_overflow: bool = False
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
    gate_time_s: Optional[float] = None
    freq_period_timeout: Optional[str] = None
    current_terminal: Optional[int] = None


@dataclass
class _RunHandle:
    run_id: str
    resource: str
    csv_path: Path | None
    measurement: str
    trigger_mode: str
    control_plane: "_WebControlPlane"
    csv_enabled: bool = True
    ready_event: threading.Event = field(default_factory=threading.Event)
    worker: threading.Thread | None = None
    state: str = "starting"
    latest_status: str = "starting"
    captured: int = 0
    errors: int = 0
    fatal_error: str | None = None
    cleanup_status: str | None = None
    trigger_count_infinite: bool = False
    expected_readings: int | None = None
    overflow_monitoring: str = "off"
    overflow_detected: bool | None = None
    stop_reason: str = "unknown"
    final_drain_complete: bool | None = None
    data_integrity: str = "unknown"
    result: StartRunResult | None = None
    warnings: list[str] = field(default_factory=list)
    cleanup_messages: list[str] = field(default_factory=list)
    recent_samples: deque[dict[str, Any]] = field(
        default_factory=lambda: deque(maxlen=LIVE_SAMPLE_CAPACITY)
    )
    worker_done: bool = False


class WebRunError(RuntimeError):
    status_code = 500


class RunAlreadyActive(WebRunError):
    status_code = 409


class RunValidationError(WebRunError):
    status_code = 422


class RunConnectionError(WebRunError):
    status_code = 503


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
        self._stop_requested = False

    def start(
        self,
        *,
        router: Any,
        port: int,  # noqa: ARG002
        min_interval_ms: int,
        queue_max: int,
        stop_cb: Callable[[], None],
        status_provider: Callable[[], dict[str, object]],  # noqa: ARG002
        run_id: str,  # noqa: ARG002
    ) -> StartControlPlaneHandle:
        with self._lock:
            self._router = router
            self._stop_cb = stop_cb
            self._queue_max = max(0, int(queue_max))
            self._min_interval_ms = max(0, int(min_interval_ms))
            self._closed = False
            deliver_stop = self._stop_requested
            self._stop_requested = False
        if deliver_stop:
            self._deliver_stop(router, stop_cb)
        self._ready_cb()
        return StartControlPlaneHandle(_stop_fn=self.close)

    def send_command(self, command: SoftwareTriggerCommand) -> tuple[bool, str]:
        with self._lock:
            if self._closed or self._router is None:
                return False, "run_not_ready"
            accepted, reason = self._try_accept_trigger_locked()
            if not accepted:
                return False, reason
            published = self._router.publish(
                TriggerEvent.new(TriggerSource.SOFTWARE, command.metadata)
            )
            if not published:
                return False, "queue_full"
            return True, ""

    def stop_run(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._stop_requested = True
            router = self._router
            stop_cb = self._stop_cb
            deliver_stop = router is not None and stop_cb is not None
            if deliver_stop:
                self._stop_requested = False
        if deliver_stop:
            self._deliver_stop(router, stop_cb)

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._router = None
            self._stop_cb = None
            self._stop_requested = False

    @staticmethod
    def _deliver_stop(router: Any, stop_cb: Callable[[], None]) -> None:
        router.publish(TriggerEvent.new(TriggerSource.SOFTWARE, {"control": "stop"}))
        stop_cb()

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
        from meters_tool_webui._desktop import (
            open_with_default_app,
            select_directory_with_dialog,
        )

        self._runner_dependencies = runner_dependencies
        self._csv_opener = csv_opener or open_with_default_app
        self._directory_selector = directory_selector or select_directory_with_dialog
        self._lock = threading.Lock()
        self._active: _RunHandle | None = None
        self._starting = False
        self._shutdown_requested = False
        self._last_status = self._idle_status()
        self._status_version = 0
        self._status_cv = threading.Condition(self._lock)
        self._close_event_streams = False

    def _publish_status_locked(self, handle_or_status: _RunHandle | dict[str, Any]) -> None:
        if isinstance(handle_or_status, _RunHandle):
            self._last_status = self._status_from_handle(handle_or_status)
        else:
            self._last_status = dict(handle_or_status)
        self._status_version += 1
        self._status_cv.notify_all()

    def close_event_streams(self) -> None:
        with self._lock:
            self._close_event_streams = True
            self._status_cv.notify_all()

    def shutdown(self, timeout_s: float = 5.0) -> bool:
        timeout_s = max(0.0, float(timeout_s))
        deadline = time.monotonic() + timeout_s
        with self._lock:
            self._shutdown_requested = True
            handle = self._active
            active = handle is not None and self._is_handle_active(handle)
            should_stop = active and handle.state != "stopping"
            worker = handle.worker if active else None

        if should_stop:
            self.stop()
        if worker is not None and worker is not threading.current_thread():
            worker.join(
                timeout=min(timeout_s, max(0.0, deadline - time.monotonic()))
            )

        with self._status_cv:
            shutdown_complete = self._status_cv.wait_for(
                lambda: not self._starting
                and (
                    self._active is None
                    or not self._is_handle_active(self._active)
                ),
                timeout=max(0.0, deadline - time.monotonic()),
            )
            if shutdown_complete:
                self._close_event_streams = True
                self._status_cv.notify_all()
            return shutdown_complete

    def iter_status_events(self) -> Iterator[str]:
        with self._lock:
            last_version = self._status_version
            current_status = dict(self._last_status)

        yield _format_status_event(last_version, current_status)

        while True:
            with self._lock:
                if self._close_event_streams:
                    break
                while (
                    self._status_version == last_version
                    and not self._close_event_streams
                ):
                    signaled = self._status_cv.wait(timeout=SSE_KEEPALIVE_INTERVAL_S)
                    if not signaled:
                        break

                if self._close_event_streams:
                    break

                if self._status_version > last_version:
                    last_version = self._status_version
                    current_status = dict(self._last_status)
                    should_send_status = True
                else:
                    should_send_status = False

            if should_send_status:
                yield _format_status_event(last_version, current_status)
            else:
                yield _format_keepalive_event()

    def capabilities(self, instrument_model: str | None = None) -> dict[str, Any]:
        auto_unresolved = instrument_model is None or not str(instrument_model).strip()
        profile = resolve_instrument_profile(instrument_model)
        return build_capabilities_payload(
            profile,
            auto_unresolved=auto_unresolved,
            package_name=PACKAGE_NAME,
            package_version=get_webui_version(),
        )

    def list_resources(
        self, verify: bool = False, live_only: bool = False, visa_library: str | None = None
    ) -> dict[str, Any]:
        if visa_library not in (None, "", "@py"):
            raise RunValidationError("visa_library must be empty or @py")
        backend_options = {"visa_library": visa_library} if visa_library else {}
        effective_verify = bool(verify or live_only)
        resources: list[dict[str, Any]] = []
        for resource in VisaInstrument.list_resources(**backend_options):
            if visa_library == "@py" and VisaInstrument.infer_transport(resource) != Transport.LAN:
                continue
            if not effective_verify:
                resources.append({"resource": resource})
                continue
            live, detail = VisaInstrument.verify_resource(resource, **backend_options)
            if live_only and not live:
                continue
            resources.append(
                {
                    "resource": resource,
                    "live": live,
                    "status": "live" if live else "stale",
                    "detail": detail,
                    **resource_model_metadata(detail if live else None),
                }
            )
        return {
            "resources": resources,
            "verify": effective_verify,
            "live_only": bool(live_only),
        }

    def start(self, request: RunStartRequest) -> dict[str, Any]:
        with self._lock:
            if self._shutdown_requested:
                raise RunAlreadyActive("WebUI is shutting down")
            if self._starting or (
                self._active is not None and self._is_handle_active(self._active)
            ):
                raise RunAlreadyActive("a run is already active")
            self._starting = True

        handle: _RunHandle | None = None
        try:
            start_request = self._normalize_request_payload(request)
            if (
                not start_request.simulate
                and start_request.visa_library == "@py"
                and VisaInstrument.infer_transport(start_request.resource) != Transport.LAN
            ):
                raise RunValidationError("PyVISA-py (@py) supports TCPIP resources only")
            start_request, profile = resolve_start_profile(start_request)
            trigger_mode = resolve_trigger_mode(start_request)
            validate_start_request(
                start_request,
                trigger_mode,
                instrument_profile=profile,
            )
            validate_start_workflow_support(start_request, trigger_mode, profile)
            warnings = generate_buffer_overflow_warnings(start_request, trigger_mode, profile)
            plan = build_start_plan(
                start_request,
                trigger_mode,
                profile,
                buffer_warnings=warnings,
            )
            runtime_request = replace(start_request, csv=plan.csv_path)
            with self._lock:
                if self._shutdown_requested:
                    raise RunAlreadyActive("WebUI is shutting down")
                run_id = str(uuid4())
                control_plane = _WebControlPlane(lambda: self._mark_handle_ready(run_id))
                handle = _RunHandle(
                    run_id=run_id,
                    resource=runtime_request.resource,
                    csv_path=Path(plan.csv_path) if plan.csv_path is not None else None,
                    measurement=plan.measurement_name,
                    trigger_mode=trigger_mode,
                    control_plane=control_plane,
                    csv_enabled=plan.csv_enabled,
                    warnings=warnings,
                )
                worker = threading.Thread(
                    target=self._run_worker,
                    args=(handle, runtime_request, profile),
                    name=f"meters-tool-web-run-{run_id}",
                    daemon=True,
                )
                handle.worker = worker
                self._active = handle
                worker.start()
                self._publish_status_locked(handle)
            handle.ready_event.wait(timeout=max(runtime_request.timeout_ms / 1000.0 + 1.0, 2.0))
            status = self.status()
            with self._lock:
                self._starting = False
                self._status_cv.notify_all()
                result = handle.result
                if result is not None and not result.ok and result.reason == "connect_error":
                    self._active = None
                    self._publish_status_locked(status)
                    raise RunConnectionError(
                        _webui_connection_error_message(
                            result.fatal_error or "connect_error",
                            profile.model,
                        )
                    )
                if result is not None and not result.ok and result.reason == "validation_error":
                    self._active = None
                    self._publish_status_locked(status)
                    raise RunValidationError(result.fatal_error or "validation_error")
            return status
        except ValueError as exc:
            with self._lock:
                self._starting = False
                self._status_cv.notify_all()
                if handle is not None and self._active is handle:
                    self._active = None
            raise RunValidationError(str(exc)) from exc
        except InstrumentError as exc:
            with self._lock:
                self._starting = False
                self._status_cv.notify_all()
                if handle is not None and self._active is handle:
                    self._active = None
            raise RunConnectionError(str(exc)) from exc
        except Exception:
            with self._lock:
                self._starting = False
                self._status_cv.notify_all()
                if handle is not None and self._active is handle and not self._is_handle_active(handle):
                    self._active = None
            raise

    def plan(self, request: RunStartRequest) -> dict[str, Any]:
        if not request.instrument_model:
            raise RunValidationError("instrument_model is required for dry-run planning")
        start_request = replace(
            self._normalize_request_payload(request),
            dry_run=True,
            simulate=False,
        )
        try:
            start_request, profile = resolve_start_profile(start_request)
            trigger_mode = resolve_trigger_mode(start_request)
            validate_start_request(
                start_request,
                trigger_mode,
                instrument_profile=profile,
            )
            validate_start_workflow_support(start_request, trigger_mode, profile)
            warnings = generate_buffer_overflow_warnings(
                start_request,
                trigger_mode,
                profile,
            )
            return asdict(
                build_start_plan(
                    start_request,
                    trigger_mode,
                    profile,
                    buffer_warnings=warnings,
                )
            )
        except ValueError as exc:
            raise RunValidationError(str(exc)) from exc

    def status(self) -> dict[str, Any]:
        with self._lock:
            if self._active is None:
                return dict(self._last_status)
            status = self._status_from_handle(self._active)
            self._last_status = status
            return dict(status)

    def send_software_trigger(
        self,
        command: SoftwareTriggerCommand,
    ) -> tuple[int, dict[str, Any]]:
        with self._lock:
            handle = self._active
            if handle is None or not self._is_handle_active(handle):
                return 409, {
                    "status": "error",
                    "error": "no_active_run",
                    "message": "no active run",
                }
        accepted, reason = handle.control_plane.send_command(command)
        if not accepted:
            if reason == "run_not_ready":
                return 409, {
                    "status": "error",
                    "error": reason,
                    "message": "run is not ready",
                }
            return 429, {"status": "rejected", "reason": reason}
        with self._lock:
            handle.latest_status = "software trigger queued"
            self._publish_status_locked(handle)
        return 202, {
            "status": "accepted",
            "message": "software trigger queued",
        }

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
                self._publish_status_locked(handle)
                return dict(self._last_status)
        control_plane.stop_run()
        with self._lock:
            self._publish_status_locked(handle)
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

    def _normalize_request_payload(self, request: RunStartRequest) -> StartRequest:
        try:
            raw = normalize_run_request_values(request)
        except ValueError as exc:
            raise RunValidationError(str(exc)) from exc

        return StartRequest(**raw)

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
                handle.trigger_count_infinite = result.trigger_count_infinite
                handle.expected_readings = result.expected_readings
                handle.overflow_monitoring = result.overflow_monitoring
                handle.overflow_detected = result.overflow_detected
                handle.stop_reason = result.stop_reason
                handle.final_drain_complete = result.final_drain_complete
                handle.data_integrity = result.data_integrity
                handle.state = "stopped" if result.ok else "error"
                if result.ok:
                    handle.latest_status = "recording stopped"
                elif result.fatal_error:
                    handle.latest_status = result.fatal_error
                else:
                    handle.latest_status = result.reason
                self._publish_status_locked(handle)
        except ValueError as exc:
            result = StartRunResult(
                run_id=handle.run_id,
                ok=False,
                reason="validation_error",
                captured=0,
                errors=0,
                fatal_error=str(exc),
                csv_path=str(handle.csv_path) if handle.csv_path is not None else None,
            )
            with self._lock:
                handle.result = result
                handle.fatal_error = result.fatal_error
                handle.latest_status = result.fatal_error or result.reason
                handle.state = "error"
                self._publish_status_locked(handle)
        except Exception as exc:  # pragma: no cover - defensive runtime boundary
            with self._lock:
                handle.fatal_error = f"{type(exc).__name__}: {exc}"
                handle.latest_status = handle.fatal_error
                handle.state = "error"
                self._publish_status_locked(handle)
        finally:
            with self._lock:
                handle.worker_done = True
                handle.ready_event.set()
                self._publish_status_locked(handle)

    def _record_event(self, event: StartRunEvent) -> None:
        with self._lock:
            handle = self._active
            if handle is None or event.run_id != handle.run_id:
                return
            if event.event in {"message", "status", "error"} and event.message:
                handle.latest_status = event.message
            if event.event == "sample":
                handle.captured = int(event.captured or handle.captured)
                payload = sample_payload(event.sample, handle.captured)
                if payload is not None:
                    handle.recent_samples.append(payload)
            if event.event in {"status", "summary"}:
                for name in (
                    "trigger_count_infinite",
                    "expected_readings",
                    "overflow_monitoring",
                    "overflow_detected",
                    "stop_reason",
                    "final_drain_complete",
                    "data_integrity",
                ):
                    if name in event.fields:
                        setattr(handle, name, event.fields[name])
            if event.event == "summary":
                handle.captured = int(event.captured or 0)
                handle.errors = int(event.errors or 0)
                handle.fatal_error = event.fatal_error
            if event.event == "error":
                handle.fatal_error = event.message
                handle.state = "error"
            if event.event == "message" and event.message:
                self._record_cleanup_message(handle, event.message)
            self._publish_status_locked(handle)

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
            self._publish_status_locked(self._active)

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
            "csv_enabled": handle.csv_enabled,
            "csv_path": str(handle.csv_path) if handle.csv_path is not None else None,
            "captured": handle.captured,
            "errors": handle.errors,
            "latest_status": handle.latest_status,
            "fatal_error": handle.fatal_error,
            "cleanup_status": handle.cleanup_status,
            "trigger_count_infinite": handle.trigger_count_infinite,
            "expected_readings": handle.expected_readings,
            "overflow_monitoring": handle.overflow_monitoring,
            "overflow_detected": handle.overflow_detected,
            "stop_reason": handle.stop_reason,
            "final_drain_complete": handle.final_drain_complete,
            "data_integrity": handle.data_integrity,
            "warnings": list(handle.warnings),
            "latest_sample": dict(recent_samples[-1]) if recent_samples else None,
            "recent_samples": recent_samples,
            "sample_capacity": LIVE_SAMPLE_CAPACITY,
        }

    def _is_handle_active(self, handle: _RunHandle) -> bool:
        if handle.worker_done:
            return False
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
            "csv_enabled": None,
            "csv_path": None,
            "captured": 0,
            "errors": 0,
            "latest_status": "idle",
            "fatal_error": None,
            "cleanup_status": None,
            "trigger_count_infinite": False,
            "expected_readings": None,
            "overflow_monitoring": "off",
            "overflow_detected": None,
            "stop_reason": "unknown",
            "final_drain_complete": None,
            "data_integrity": "unknown",
            "warnings": [],
            "latest_sample": None,
            "recent_samples": [],
            "sample_capacity": LIVE_SAMPLE_CAPACITY,
        }


def _format_status_event(version: int, status: dict[str, Any]) -> str:
    return (
        f"event: {SSE_EVENT_NAME}\n"
        f"id: {version}\n"
        f"data: {json.dumps(status, separators=(',', ':'))}\n\n"
    )


def _format_keepalive_event() -> str:
    return ": keepalive\n\n"


def get_webui_version() -> str:
    return get_distribution_version(
        distribution_name=DISTRIBUTION_NAME,
        fallback=FALLBACK_WEBUI_VERSION,
    )


def _webui_connection_error_message(message: str, selected_model: str) -> str:
    if "unsupported instrument identity; expected Keysight/Agilent" not in message:
        return message
    marker = "got '"
    start = message.find(marker)
    if start < 0:
        return message
    start += len(marker)
    end = message.find("'", start)
    if end < 0:
        return message
    idn = message[start:end]
    try:
        connected_profile = find_instrument_profile_by_idn(idn)
    except ValueError:
        return message
    if connected_profile.model == selected_model:
        return message
    return (
        f"Selected model {selected_model} does not match the connected instrument "
        f"IDN {connected_profile.model}. Select {connected_profile.model} or rescan the device."
    )


