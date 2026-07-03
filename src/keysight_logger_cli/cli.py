from __future__ import annotations

import argparse
import ctypes
import json
import signal
import sys
from datetime import datetime, timezone

from keysight_logger_core._version import (
    DISTRIBUTION_NAME,
    FALLBACK_PACKAGE_VERSION,
    get_distribution_version,
)
from keysight_logger_core.instrument import VisaInstrument
from keysight_logger_core.models import StartRequest, resolve_instrument_profile
from keysight_logger_core.runner import StopController, run_start_session
from keysight_logger_core.run_plan import StartPlan, build_start_plan
from keysight_logger_core.session import StartRunEvent, new_run_id
from keysight_logger_core.validation import (
    generate_buffer_overflow_warnings,
    resolve_trigger_mode,
    validate_start_request,
)
try:
    from ._client_commands import (
        CommandResponsePayloadError,
        StatusPayloadError,
        _validate_client_port_and_timeout,
        cmd_send_command,
        cmd_status,
        cmd_stop,
        cmd_wait_ready,
        validate_client_timeout_ms,
    )
    from ._parser import (
        KeysightArgumentParser,
        KeysightHelpFormatter,
        build_parser as _build_parser,
        parse_auto_zero,
        parse_dcv_input_impedance,
        parse_on_off,
    )
except ImportError:  # pragma: no cover - PyInstaller script entry point
    from keysight_logger_cli._client_commands import (
        CommandResponsePayloadError,
        StatusPayloadError,
        _validate_client_port_and_timeout,
        cmd_send_command,
        cmd_status,
        cmd_stop,
        cmd_wait_ready,
        validate_client_timeout_ms,
    )
    from keysight_logger_cli._parser import (
        KeysightArgumentParser,
        KeysightHelpFormatter,
        build_parser as _build_parser,
        parse_auto_zero,
        parse_dcv_input_impedance,
        parse_on_off,
    )

CLI_EVENT_SCHEMA_VERSION = 1
FALLBACK_CLI_VERSION = FALLBACK_PACKAGE_VERSION


def get_cli_version() -> str:
    return get_distribution_version(
        distribution_name=DISTRIBUTION_NAME,
        fallback=FALLBACK_CLI_VERSION,
    )


class WindowsConsoleStopHandler:
    _CTRL_C_EVENT = 0
    _CTRL_BREAK_EVENT = 1
    _STD_INPUT_HANDLE = -10
    _ENABLE_PROCESSED_INPUT = 0x0001

    def __init__(self, stop_controller: StopController):
        self._stop_controller = stop_controller
        self._kernel32 = None
        self._handler = None
        self._stdin_handle = None
        self._previous_input_mode = None
        self.installed = False
        self.input_mode_configured = False

    def install(self) -> bool:
        if sys.platform != "win32":
            return False
        try:
            from ctypes import wintypes

            self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)
            self._kernel32.SetConsoleCtrlHandler.argtypes = (callback_type, wintypes.BOOL)
            self._kernel32.SetConsoleCtrlHandler.restype = wintypes.BOOL
            self._kernel32.GetStdHandle.argtypes = (wintypes.DWORD,)
            self._kernel32.GetStdHandle.restype = wintypes.HANDLE
            self._kernel32.GetConsoleMode.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
            self._kernel32.GetConsoleMode.restype = wintypes.BOOL
            self._kernel32.SetConsoleMode.argtypes = (wintypes.HANDLE, wintypes.DWORD)
            self._kernel32.SetConsoleMode.restype = wintypes.BOOL
            self._configure_input_mode(wintypes)
            self._handler = callback_type(self._handle)
            if not self._kernel32.SetConsoleCtrlHandler(self._handler, True):
                return False
        except (AttributeError, OSError):
            return False
        self.installed = True
        return True

    def uninstall(self) -> None:
        if not self.installed or self._kernel32 is None or self._handler is None:
            return
        self._restore_input_mode()
        self._kernel32.SetConsoleCtrlHandler(self._handler, False)
        self.installed = False

    def _handle(self, ctrl_type: int) -> bool:
        if ctrl_type not in (self._CTRL_C_EVENT, self._CTRL_BREAK_EVENT):
            return False
        self._stop_controller.request_signal_stop()
        return True

    def _configure_input_mode(self, wintypes) -> None:  # noqa: ANN001
        if self._kernel32 is None:
            return
        handle = self._kernel32.GetStdHandle(self._STD_INPUT_HANDLE)
        if not handle:
            return
        mode = wintypes.DWORD()
        if not self._kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return
        self._stdin_handle = handle
        self._previous_input_mode = int(mode.value)
        desired_mode = int(mode.value) | self._ENABLE_PROCESSED_INPUT
        if self._kernel32.SetConsoleMode(handle, desired_mode):
            self.input_mode_configured = True

    def _restore_input_mode(self) -> None:
        if (
            self._kernel32 is None
            or self._stdin_handle is None
            or self._previous_input_mode is None
            or not self.input_mode_configured
        ):
            return
        self._kernel32.SetConsoleMode(self._stdin_handle, self._previous_input_mode)
        self.input_mode_configured = False

class WindowsKeyboardStopPoller:
    def __init__(self):
        self._msvcrt = None
        if sys.platform == "win32":
            try:
                import msvcrt

                self._msvcrt = msvcrt
            except ImportError:
                self._msvcrt = None

    def poll_stop_requested(self) -> bool:
        if self._msvcrt is None:
            return False
        requested = False
        while self._msvcrt.kbhit():
            ch = self._msvcrt.getwch()
            if ch in ("\x00", "\xe0"):
                if self._msvcrt.kbhit():
                    self._msvcrt.getwch()
                continue
            if ch in ("\x03", "q", "Q"):
                requested = True
        return requested

class CliStartRunControls:
    def __init__(
        self,
        console_handler_factory=WindowsConsoleStopHandler,  # noqa: ANN001
        keyboard_poller_factory=WindowsKeyboardStopPoller,  # noqa: ANN001
    ) -> None:
        self._console_handler_factory = console_handler_factory
        self._keyboard_poller_factory = keyboard_poller_factory
        self._stop_controller: StopController | None = None
        self._previous_signal_handlers = []
        self._windows_console_stop_handler = None
        self._keyboard_stop_poller = None

    def install(self, stop_controller: StopController) -> None:
        self._stop_controller = stop_controller

        def handle_stop_signal(signum, frame):  # noqa: ARG001
            stop_controller.request_signal_stop()

        self._previous_signal_handlers.append(
            (signal.SIGINT, signal.signal(signal.SIGINT, handle_stop_signal))
        )
        if hasattr(signal, "SIGTERM"):
            self._previous_signal_handlers.append(
                (signal.SIGTERM, signal.signal(signal.SIGTERM, handle_stop_signal))
            )
        if hasattr(signal, "SIGBREAK"):
            self._previous_signal_handlers.append(
                (signal.SIGBREAK, signal.signal(signal.SIGBREAK, handle_stop_signal))
            )
        self._windows_console_stop_handler = self._console_handler_factory(stop_controller)
        self._keyboard_stop_poller = self._keyboard_poller_factory()

    def after_connect(self, event_sink, run_id: str) -> None:  # noqa: ANN001
        if self._windows_console_stop_handler is None:
            return
        if self._windows_console_stop_handler.install():
            event_sink.emit(
                StartRunEvent.message_event(
                    run_id,
                    "windows console stop handler: installed "
                    f"processed_input={self._windows_console_stop_handler.input_mode_configured}",
                )
            )
        elif sys.platform == "win32":
            event_sink.emit(
                StartRunEvent.error_event(run_id, "windows console stop handler: unavailable")
            )

    def poll_stop_requested(self) -> bool:
        if self._keyboard_stop_poller is None:
            return False
        return bool(self._keyboard_stop_poller.poll_stop_requested())

    def uninstall(self) -> None:
        if self._windows_console_stop_handler is not None:
            self._windows_console_stop_handler.uninstall()
        for sig, previous_handler in self._previous_signal_handlers:
            signal.signal(sig, previous_handler)
        self._previous_signal_handlers = []

class CliEventEmitter:
    def __init__(self, print_fn=print, output_format: str = "text") -> None:  # noqa: ANN001
        self._print = print_fn
        self._output_format = output_format

    @property
    def output_format(self) -> str:
        return self._output_format

    def _emit_json(self, payload: dict) -> None:
        self._print(json.dumps(payload, sort_keys=True))

    def status(self, message: str, **fields) -> None:  # noqa: ANN003
        if self._output_format == "jsonl":
            payload = {
                "event": "status",
                "message": message,
                "schema_version": CLI_EVENT_SCHEMA_VERSION,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            }
            payload.update(fields)
            self._emit_json(payload)
            return
        self._print(f"[status] {message}")

    def sample(self, sample, captured: int, **fields) -> None:  # noqa: ANN001, ANN003
        if self._output_format == "jsonl":
            payload = {
                "captured": captured,
                "event": "sample",
                "measurement_type": sample.measurement_type,
                "measurement_metadata": sample.measurement_metadata,
                "message": f"value={sample.value:g} {sample.unit}",
                "resource_id": sample.resource_id,
                "schema_version": CLI_EVENT_SCHEMA_VERSION,
                "status": sample.status,
                "timestamp_utc": sample.timestamp_utc.isoformat(),
                "trigger_id": sample.trigger_id,
                "trigger_metadata": sample.trigger_metadata,
                "trigger_source": sample.trigger_source,
                "unit": sample.unit,
                "value": sample.value,
            }
            payload.update(fields)
            self._emit_json(payload)

    def summary(
        self,
        captured: int,
        errors: int,
        fatal_error: str | None = None,
        **fields,  # noqa: ANN003
    ) -> None:
        if self._output_format == "jsonl":
            payload = {
                "captured": captured,
                "errors": errors,
                "event": "summary",
                "ok": fatal_error is None,
                "schema_version": CLI_EVENT_SCHEMA_VERSION,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            }
            if fatal_error is not None:
                payload["fatal_error"] = fatal_error
            payload.update(fields)
            self._emit_json(payload)
            return
        self._print(f"captured={captured} errors={errors}")

    def ready(self, host: str, port: int, **fields) -> None:  # noqa: ANN003
        if self._output_format != "jsonl":
            return
        base_url = f"http://{host}:{port}"
        payload = {
            "event": "ready",
            "host": host,
            "port": port,
            "schema_version": CLI_EVENT_SCHEMA_VERSION,
            "service": "keysight-meter",
            "status_url": f"{base_url}/status",
            "stop_url": f"{base_url}/stop",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "command_url": f"{base_url}/command",
        }
        payload.update(fields)
        self._emit_json(payload)

    def line(self, message: str, **fields) -> None:  # noqa: ANN003
        if self._output_format == "jsonl":
            payload = {
                "event": "message",
                "message": message,
                "schema_version": CLI_EVENT_SCHEMA_VERSION,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            }
            payload.update(fields)
            self._emit_json(payload)
            return
        self._print(message)

    def error(self, message: str, rc: int = 3, **fields) -> None:  # noqa: ANN003
        if self._output_format == "jsonl":
            payload = {
                "event": "error",
                "message": message,
                "schema_version": CLI_EVENT_SCHEMA_VERSION,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "exit_code": rc,
            }
            payload.update(fields)
            self._emit_json(payload)
            return
        self._print(message, file=sys.stderr)

class CliStartRunEventSink:
    def __init__(self, emitter: CliEventEmitter) -> None:
        self._emitter = emitter

    def _runtime_fields(self, event: StartRunEvent) -> dict[str, object]:
        return {"run_id": event.run_id} if event.run_id is not None else {}

    def emit(self, event: StartRunEvent) -> None:
        fields = self._runtime_fields(event)
        if event.event == "status":
            fields.update(event.fields)
            self._emitter.status(event.message or "", **fields)
            return
        if event.event == "sample":
            self._emitter.sample(event.sample, int(event.captured or 0), **fields)
            return
        if event.event == "summary":
            self._emitter.summary(
                int(event.captured or 0),
                int(event.errors or 0),
                event.fatal_error,
                **fields,
            )
            return
        if event.event == "ready":
            if event.host is not None and event.port is not None:
                ready_fields = dict(fields)
                if event.command_url is not None:
                    ready_fields["command_url"] = event.command_url
                if event.stop_url is not None:
                    ready_fields["stop_url"] = event.stop_url
                if event.status_url is not None:
                    ready_fields["status_url"] = event.status_url
                self._emitter.ready(event.host, event.port, **ready_fields)
            return
        if event.event == "error":
            self._emitter.error(event.message or "", rc=3, **fields)
            return
        self._emitter.line(event.message or "", **fields)

def _emit_start_plan(plan: StartPlan, emitter: CliEventEmitter) -> None:
    if emitter.output_format == "jsonl":
        emitter._emit_json(
            {
                "dry_run_performs_visa_io": False,
                "dry_run_starts_http_server": False,
                "dry_run_writes_csv": False,
                "event": "dry_run",
                "schema_version": CLI_EVENT_SCHEMA_VERSION,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "trigger_mode": plan.trigger_mode,
                "measurement_type": plan.measurement_type,
                "measurement_cli_name": plan.measurement_name,
                "measurement_unit": plan.measurement_unit,
                "csv_path": plan.csv_path,
                "resource": plan.resource,
                "simulate": plan.simulate,
                "dry_run": plan.dry_run,
                "scpi_commands": plan.scpi_commands,
                "read_path": plan.read_path,
                "cleanup_steps": plan.cleanup_steps,
                "notes": plan.notes,
            }
        )
        return
    emitter.line("dry-run plan:")
    emitter.line("  performs VISA I/O: false")
    emitter.line("  writes CSV: false")
    emitter.line("  starts HTTP server: false")
    emitter.line(f"  resource: {plan.resource}")
    emitter.line(f"  measurement: {plan.measurement_name} ({plan.measurement_unit})")
    emitter.line(f"  trigger_mode: {plan.trigger_mode}")
    emitter.line(f"  csv_path: {plan.csv_path}")
    emitter.line(f"  simulate: {plan.simulate}")
    emitter.line("  scpi:")
    for command in plan.scpi_commands:
        emitter.line(f"    {command}")
    emitter.line(f"  read_path: {plan.read_path}")
    emitter.line(f"  cleanup: {', '.join(plan.cleanup_steps)}")
    for note in plan.notes:
        emitter.line(f"  note: {note}")

def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None

def _start_request_from_args(args: argparse.Namespace) -> StartRequest:
    return StartRequest(
        resource=args.resource,
        instrument_model=args.instrument_model,
        visa_library=_optional_text(args.visa_library),
        csv=args.csv,
        dry_run=args.dry_run,
        simulate=args.simulate,
        timeout_ms=args.timeout_ms,
        trigger_timeout_ms=args.trigger_timeout_ms,
        sw_trigger_port=args.sw_trigger_port,
        sw_min_interval_ms=args.sw_min_interval_ms,
        sw_queue_max=args.sw_queue_max,
        trigger_mode=args.trigger_mode,
        max_samples=args.max_samples,
        trigger_count=args.trigger_count,
        sample_count=args.sample_count,
        timer_interval_s=args.timer_interval_s,
        buffer_drain_size=args.buffer_drain_size,
        allow_buffer_overflow_risk=args.allow_buffer_overflow_risk,
        hw_trigger_slope=args.hw_trigger_slope,
        hw_trigger_delay_s=args.hw_trigger_delay_s,
        measurement=args.measurement,
        nplc=args.nplc,
        auto_zero=args.auto_zero,
        auto_range=args.auto_range,
        measurement_range=args.measurement_range,
        current_range=args.current_range,
        ac_bandwidth_hz=args.ac_bandwidth_hz,
        gate_time_s=args.gate_time_s,
        freq_period_timeout=args.freq_period_timeout,
        current_terminal=args.current_terminal,
        dcv_input_impedance=args.dcv_input_impedance,
        vm_comp_slope=args.vm_comp_slope,
    )

def build_parser() -> argparse.ArgumentParser:
    return _build_parser(get_cli_version)

def cmd_list_resources(
    verify: bool = False,
    live_only: bool = False,
    output_format: str = "text",
    dry_run: bool = False,
    visa_library: str | None = None,
    print_fn=print,  # noqa: ANN001
    resource_manager_factory=None,  # noqa: ANN001
) -> int:
    if output_format not in {"text", "json"}:
        raise ValueError("output_format must be 'text' or 'json'")

    effective_verify = verify or live_only
    normalized_visa_library = _optional_text(visa_library)
    if dry_run:
        payload = {
            "command": "list-resources",
            "dry_run_performs_visa_io": False,
            "effective_verify": effective_verify,
            "event": "dry_run",
            "live_only": live_only,
            "output_format": output_format,
            "planned_real_run": {
                "close_each_resource": effective_verify,
                "filter_live_only": live_only,
                "list_visa_resources": True,
                "open_each_resource": effective_verify,
                "query_idn": effective_verify,
                "release_to_local_after_successful_verify": effective_verify,
            },
            "schema_version": CLI_EVENT_SCHEMA_VERSION,
            "status": "dry_run",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "visa_library": normalized_visa_library,
            "verify": verify,
        }
        if output_format == "json":
            print_fn(json.dumps(payload, sort_keys=True))
        else:
            actions = payload["planned_real_run"]
            print_fn("dry-run list-resources:")
            print_fn(f"  output_format: {output_format}")
            print_fn(f"  verify: {str(verify).lower()}")
            print_fn(f"  live_only: {str(live_only).lower()}")
            print_fn(f"  visa_library: {normalized_visa_library or 'default'}")
            print_fn(f"  effective_verify: {str(effective_verify).lower()}")
            print_fn("  dry_run_performs_visa_io: false")
            print_fn("  VISA I/O: no")
            print_fn("  planned real-run actions:")
            print_fn(f"    list VISA resources: {'yes' if actions['list_visa_resources'] else 'no'}")
            print_fn(f"    open each resource: {'yes' if actions['open_each_resource'] else 'no'}")
            print_fn(f"    query *IDN?: {'yes' if actions['query_idn'] else 'no'}")
            print_fn(
                "    release_to_local after successful verify: "
                f"{'yes' if actions['release_to_local_after_successful_verify'] else 'no'}"
            )
            print_fn(f"    close each resource: {'yes' if actions['close_each_resource'] else 'no'}")
            print_fn(f"    filter live-only: {'yes' if actions['filter_live_only'] else 'no'}")
        return 0

    resources = []
    text_rows = 0
    for resource in VisaInstrument.list_resources(
        resource_manager_factory=resource_manager_factory,
        visa_library=normalized_visa_library,
    ):
        if not effective_verify:
            if output_format == "text":
                print_fn(resource)
                text_rows += 1
            else:
                resources.append({"resource": resource})
            continue
        ok, detail = VisaInstrument.verify_resource(
            resource,
            resource_manager_factory=resource_manager_factory,
            visa_library=normalized_visa_library,
        )
        if live_only and not ok:
            continue
        status = "live" if ok else "stale"
        if output_format == "text":
            print_fn(f"{status}\t{resource}\t{detail}")
            text_rows += 1
        else:
            resources.append(
                {
                    "detail": detail,
                    "live": ok,
                    "resource": resource,
                    "status": status,
                }
            )
    if live_only and output_format == "text" and text_rows == 0:
        print_fn("no live VISA resources found")
    if output_format == "json":
        live_count = sum(1 for resource in resources if resource.get("live") is True)
        stale_count = sum(1 for resource in resources if resource.get("live") is False)
        payload = {
            "count": len(resources),
            "diagnostic_hints": [],
            "event": "list-resources",
            "live_count": live_count,
            "resources": resources,
            "schema_version": CLI_EVENT_SCHEMA_VERSION,
            "stale_count": stale_count,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "visa_library": normalized_visa_library,
            "verify": effective_verify,
        }
        if live_only:
            payload["live_only"] = True
        if not effective_verify:
            payload["diagnostic_hints"].append("Use --verify to query *IDN? and mark live/stale resources.")
        if live_only and live_count == 0:
            payload["diagnostic_hints"].append("No live VISA resources were found by verification.")
        print_fn(
            json.dumps(
                payload,
                sort_keys=True,
            )
        )
    return 0

def cmd_start(args: argparse.Namespace) -> int:
    emitter = CliEventEmitter(print_fn=print, output_format=args.status_format)
    request_model: StartRequest
    try:
        request_model = _start_request_from_args(args)
        instrument_profile = resolve_instrument_profile(request_model.instrument_model)
        trigger_mode = resolve_trigger_mode(request_model)
        validate_start_request(request_model, trigger_mode, instrument_profile=instrument_profile)
    except ValueError as exc:
        emitter.error(str(exc), rc=2)
        return 2
    runtime_run_id = None if request_model.dry_run else new_run_id()
    warnings = generate_buffer_overflow_warnings(
        request_model,
        trigger_mode,
        instrument_profile=instrument_profile,
    )

    plan = build_start_plan(
        request_model,
        trigger_mode,
        instrument_profile,
        buffer_warnings=warnings if request_model.dry_run else None,
    )
    if request_model.dry_run:
        _emit_start_plan(plan, emitter)
        return 0

    event_sink = CliStartRunEventSink(emitter)
    assert runtime_run_id is not None
    for warning in warnings:
        if args.status_format == "jsonl":
            event_sink.emit(StartRunEvent.status_event(runtime_run_id, warning))
        else:
            emitter.line(warning)

    result = run_start_session(
        request_model,
        trigger_mode,
        instrument_profile,
        event_sink,
        CliStartRunControls(),
        run_id=runtime_run_id,
    )
    return 0 if result.ok else 3

def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "list-resources":
        return cmd_list_resources(
            verify=args.verify,
            live_only=args.live_only,
            output_format=args.output_format,
            dry_run=args.dry_run,
            visa_library=args.visa_library,
        )
    if args.command == "send-command":
        validation_rc = _validate_client_port_and_timeout(args)
        if validation_rc is not None:
            return validation_rc
        return cmd_send_command(
            args.port,
            args.arguments_json,
            args.output_format,
            args.dry_run,
            args.timeout_ms,
            command=args.command_name,
            job_id=args.job_id,
        )
    if args.command == "stop":
        validation_rc = _validate_client_port_and_timeout(args)
        if validation_rc is not None:
            return validation_rc
        return cmd_stop(args.port, args.output_format, args.dry_run, args.timeout_ms)
    if args.command == "status":
        validation_rc = _validate_client_port_and_timeout(args)
        if validation_rc is not None:
            return validation_rc
        return cmd_status(args.port, args.output_format, args.dry_run, args.timeout_ms)
    if args.command == "wait-ready":
        validation_rc = _validate_client_port_and_timeout(args)
        if validation_rc is not None:
            return validation_rc
        return cmd_wait_ready(args.port, args.output_format, args.timeout_ms)
    if args.command == "start-trigger-record":
        return cmd_start(args)
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
