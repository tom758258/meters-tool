from __future__ import annotations

from dataclasses import dataclass, field
import threading
import time
from typing import Any, Callable

from ._request_config import acquisition_config_from_start_request
from .acquisition import TriggerAcquisitionEngine
from .instrument import InstrumentError
from .instrument_backend import create_instrument_backend
from .measurement import create_measurement_plugin, normalize_measurement_type
from .models import InstrumentConfig, InstrumentProfile, StartRequest
from .session import (
    NoOpStartRunControls,
    SoftwareTriggerControlPlane,
    StartControlPlane,
    StartControlPlaneHandle,
    StartRunControls,
    StartRunEvent,
    StartRunEventSink,
    StartRunResult,
    StopController,
    new_run_id,
)
from .start_resolution import resolve_start_profile
from .storage import CsvWriter
from .support_policy import validate_start_workflow_support
from .trigger import SoftwareTriggerAdapter, TriggerRouter
from .validation import resolve_csv_path, resolve_trigger_mode, validate_start_request


@dataclass(frozen=True)
class StartRunnerDependencies:
    instrument_backend_factory: Callable[..., Any] = field(default_factory=lambda: create_instrument_backend)
    router_factory: Callable[..., Any] = field(default_factory=lambda: TriggerRouter)
    storage_factory: Callable[..., Any] = field(default_factory=lambda: CsvWriter)
    measurement_factory: Callable[..., Any] = field(default_factory=lambda: create_measurement_plugin)
    engine_factory: Callable[..., Any] = field(default_factory=lambda: TriggerAcquisitionEngine)
    server_factory: Callable[..., Any] = field(default_factory=lambda: SoftwareTriggerAdapter)
    thread_factory: Callable[..., threading.Thread] = field(default_factory=lambda: threading.Thread)
    sleep: Callable[[float], None] = field(default_factory=lambda: time.sleep)


def run_start_session(
    request: StartRequest,
    trigger_mode: str,
    profile: InstrumentProfile,
    event_sink: StartRunEventSink,
    controls: StartRunControls | None,
    control_plane: StartControlPlane | None = None,
    run_id: str | None = None,
    dependencies: StartRunnerDependencies | None = None,
) -> StartRunResult:
    request, profile = resolve_start_profile(request)
    # `trigger_mode` is retained for public API compatibility; the runner
    # recomputes the effective mode from the resolved request.
    effective_trigger_mode = resolve_trigger_mode(request)
    validate_start_request(request, effective_trigger_mode, instrument_profile=profile)
    validate_start_workflow_support(request, effective_trigger_mode, profile)

    deps = dependencies or StartRunnerDependencies()
    active_controls = controls or NoOpStartRunControls()
    active_control_plane = control_plane or SoftwareTriggerControlPlane(deps.server_factory)
    active_run_id = run_id or new_run_id()
    measurement_type = normalize_measurement_type(request.measurement)
    csv_path = resolve_csv_path(request.csv)
    if request.csv is None:
        event_sink.emit(StartRunEvent.message_event(active_run_id, f"csv output path: {csv_path}"))
    iconfig = InstrumentConfig(
        resource_string=request.resource,
        timeout_ms=request.timeout_ms,
        expected_model=profile.model,
        visa_library=request.visa_library,
    )
    aconfig = acquisition_config_from_start_request(request, measurement_type)
    instrument = deps.instrument_backend_factory(
        iconfig,
        simulate=request.simulate,
        measurement_type=measurement_type,
    )
    router = deps.router_factory(max_pending_events=request.sw_queue_max)
    storage = deps.storage_factory(csv_path)
    measurement = deps.measurement_factory(measurement_type)
    engine = deps.engine_factory(
        instrument=instrument,
        measurement=measurement,
        storage=storage,
        config=aconfig,
        router=router,
        status_cb=lambda m: event_sink.emit(StartRunEvent.status_event(active_run_id, m)),
        sample_cb=lambda sample, captured: event_sink.emit(
            StartRunEvent.sample_event(active_run_id, sample, captured)
        ),
        instrument_profile=profile,
    )

    stop_controller = StopController(engine.stop)
    runtime_fatal_error: str | None = None

    def emit_message(message: str) -> None:
        event_sink.emit(StartRunEvent.message_event(active_run_id, message))

    def emit_error(message: str) -> None:
        event_sink.emit(StartRunEvent.error_event(active_run_id, message))

    def emit_summary() -> None:
        event_sink.emit(
            StartRunEvent.summary_event(
                active_run_id,
                engine.stats.captured,
                engine.stats.errors,
                engine.fatal_error or runtime_fatal_error,
            )
        )

    def drain_stop_messages() -> None:
        for message in stop_controller.pop_messages():
            emit_message(message)

    def result(
        *,
        ok: bool,
        reason: str,
        control: StartControlPlaneHandle | None,
        fatal_error: str | None = None,
    ) -> StartRunResult:
        return StartRunResult(
            run_id=active_run_id,
            ok=ok,
            reason=reason,
            captured=engine.stats.captured,
            errors=engine.stats.errors,
            fatal_error=(
                fatal_error
                if fatal_error is not None
                else engine.fatal_error or runtime_fatal_error
            ),
            csv_path=csv_path,
            control=control,
        )

    def worker_status() -> dict[str, object]:
        return {
            "run_id": active_run_id,
            "status": "stopping" if stop_controller.stop else "running",
            "captured": engine.stats.captured,
            "errors": engine.stats.errors,
            "fatal_error": engine.fatal_error or runtime_fatal_error,
        }

    worker: threading.Thread | None = None
    connected = False
    control_handle: StartControlPlaneHandle | None = None
    active_controls.install(stop_controller)
    try:
        try:
            instrument.connect()
            connected = True
        except InstrumentError as exc:
            emit_error(f"error: {exc}")
            return result(
                ok=False,
                reason="connect_error",
                control=control_handle,
                fatal_error=str(exc),
            )
        active_controls.after_connect(event_sink, active_run_id)
        control_handle = active_control_plane.start(
            router=router,
            port=request.sw_trigger_port,
            min_interval_ms=request.sw_min_interval_ms,
            queue_max=request.sw_queue_max,
            stop_cb=stop_controller.request_http_stop,
            status_provider=worker_status,
        )
        if control_handle.active:
            emit_message(f"command endpoint: {control_handle.command_url}")
            emit_message(f"software stop endpoint: {control_handle.stop_url}")
            emit_message(f"software status endpoint: {control_handle.status_url}")
            emit_message("local stop keys: Ctrl+C, Ctrl+Break, q")
            event_sink.emit(StartRunEvent.ready_event(active_run_id, control_handle))

        def run_worker() -> None:
            nonlocal runtime_fatal_error
            try:
                engine.run(
                    trigger_mode=effective_trigger_mode,
                    hardware_trigger_slope=request.hw_trigger_slope,
                )
            except Exception as exc:
                runtime_fatal_error = str(exc)

        worker = deps.thread_factory(
            target=run_worker,
            kwargs={},
            daemon=True,
        )
        worker.start()
        try:
            while worker.is_alive() and not stop_controller.stop:
                drain_stop_messages()
                if active_controls.poll_stop_requested():
                    stop_controller.request_signal_stop()
                    drain_stop_messages()
                    break
                deps.sleep(0.2)
            drain_stop_messages()
            if not worker.is_alive() and not stop_controller.stop:
                if engine.fatal_error or runtime_fatal_error:
                    emit_error(f"error: {engine.fatal_error or runtime_fatal_error}")
                else:
                    emit_message("measurement worker exited before stop was requested")
        except KeyboardInterrupt:
            stop_controller.request_signal_stop()
            drain_stop_messages()
            while worker.is_alive():
                try:
                    worker.join(timeout=0.2)
                    if not worker.is_alive():
                        break
                except KeyboardInterrupt:
                    stop_controller.request_signal_stop()
                    drain_stop_messages()
                    break
        finally:
            emit_message("main cleanup starting")
            engine.stop()
            if worker.is_alive():
                join_timeout_s = max(request.trigger_timeout_ms / 1000.0 + 1.0, 2.0)
                emit_message(f"waiting for measurement worker to stop, timeout_s={join_timeout_s:.1f}")
                worker.join(timeout=join_timeout_s)
            if worker.is_alive() or stop_controller.force:
                emit_message(f"release_to_local before close: {instrument.release_to_local()}")
                instrument.close()
                worker.join(timeout=2)
        emit_summary()
        if engine.fatal_error or runtime_fatal_error:
            return result(ok=False, reason="fatal_error", control=control_handle)
        return result(ok=True, reason="completed", control=control_handle)
    finally:
        emit_message("final cleanup starting")
        # Ensure worker exits before final release/close.
        if worker is not None and worker.is_alive():
            emit_message("waiting worker to fully stop...")
            worker.join(timeout=5)

        # Release instrument control before closing the session.
        if connected:
            rel = instrument.release_to_local()
            emit_message(f"release_to_local: {rel}")
            # Retry once on transient session instability.
            if "SYST:LOC:failed" in rel:
                deps.sleep(1.0)
                rel2 = instrument.release_to_local()
                emit_message(f"release_to_local retry: {rel2}")
            instrument.close()
            emit_message(f"cleanup_release_to_local: {instrument.cleanup_release_to_local()}")
        emit_message("stopping software trigger server")
        if control_handle is not None:
            control_handle.stop()
        emit_message("software trigger server stopped")
        active_controls.uninstall()
