from __future__ import annotations

import argparse
import ctypes
import importlib.metadata
import json
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib import request
from urllib.error import URLError

from .core.instrument import VisaInstrument
from .core.measurement import format_measurement_type
from .core.models import StartRequest, get_default_instrument_profile
from .core.runner import StopController, run_start_session
from .core.run_plan import StartPlan, build_start_plan
from .core.session import StartRunEvent, new_run_id
from .core.validation import (
    generate_buffer_overflow_warnings,
    resolve_trigger_mode,
    start_help_epilog as _start_help_epilog,
    supported_measurement_types as _supported_measurement_types,
    validate_client_port,
    validate_start_request,
)


CLI_EVENT_SCHEMA_VERSION = 1
PACKAGE_NAME = "keysight-logger"


class KeysightHelpFormatter(
    argparse.ArgumentDefaultsHelpFormatter,
    argparse.RawDescriptionHelpFormatter,
):
    pass


class KeysightArgumentParser(argparse.ArgumentParser):
    def parse_args(self, args=None, namespace=None):  # noqa: ANN001
        raw_args = list(sys.argv[1:] if args is None else args)
        parsed = super().parse_args(args, namespace)
        _apply_json_aliases(parsed, raw_args, self)
        return parsed


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


def get_cli_version() -> str:
    try:
        return importlib.metadata.version(PACKAGE_NAME)
    except importlib.metadata.PackageNotFoundError:
        return _read_project_version()


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


def parse_on_off(value: str) -> bool:
    lower = str(value).strip().lower()
    if lower == "on":
        return True
    if lower == "off":
        return False
    raise argparse.ArgumentTypeError("value must be 'on' or 'off'")


def parse_auto_zero(value: str) -> bool | str:
    lower = str(value).strip().lower()
    if lower == "on":
        return True
    if lower == "off":
        return False
    if lower == "once":
        return "once"
    raise argparse.ArgumentTypeError("value must be 'on', 'off', or 'once'")


def parse_dcv_input_impedance(value: str) -> str:
    normalized = str(value).strip().lower()
    if normalized in {"default", "10m", "auto"}:
        return normalized
    raise argparse.ArgumentTypeError("value must be 'default', '10m', or 'auto'")


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
            "trigger_url": f"{base_url}/trigger",
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
                if event.trigger_url is not None:
                    ready_fields["trigger_url"] = event.trigger_url
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


def _option_values(argv: list[str], option: str) -> list[str]:
    values: list[str] = []
    prefix = f"{option}="
    index = 0
    while index < len(argv):
        token = argv[index]
        if token == option and index + 1 < len(argv):
            values.append(argv[index + 1])
            index += 2
            continue
        if token.startswith(prefix):
            values.append(token[len(prefix) :])
            index += 1
            continue
        index += 1
    return values


def _last_option_value(argv: list[str], option: str) -> str | None:
    values = _option_values(argv, option)
    return values[-1] if values else None


def _apply_json_aliases(args: argparse.Namespace, argv: list[str], parser: argparse.ArgumentParser) -> None:
    if getattr(args, "command", None) == "start-trigger-record":
        if not getattr(args, "json", False):
            return
        status_format = _last_option_value(argv, "--status-format")
        if status_format is not None and status_format != "jsonl":
            parser.error(f"--json conflicts with --status-format {status_format}")
        args.status_format = "jsonl"
        return
    if getattr(args, "command", None) in {"list-resources", "soft-trigger", "soft-stop"}:
        if not getattr(args, "json", False):
            return
        output_format = _last_option_value(argv, "--format")
        if output_format is not None and output_format != "json":
            parser.error(f"--json conflicts with --format {output_format}")
        args.output_format = "json"


def _start_request_from_args(args: argparse.Namespace) -> StartRequest:
    return StartRequest(
        resource=args.resource,
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
        current_terminal=args.current_terminal,
        dcv_input_impedance=args.dcv_input_impedance,
        vm_comp_slope=args.vm_comp_slope,
    )


def _emit_client_dry_run(command_name: str, port: int, body, output_format: str) -> None:  # noqa: ANN001
    payload = {
        "body": body,
        "event": "dry_run",
        "method": "POST",
        "schema_version": CLI_EVENT_SCHEMA_VERSION,
        "send_request": False,
        "status": "dry_run",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "url": f"http://127.0.0.1:{port}/{command_name.split('-')[-1]}",
    }
    if output_format == "json":
        print(json.dumps(payload, sort_keys=True))
        return
    print(f"dry-run {command_name}:")
    print(f"  method: POST")
    print(f"  url: {payload['url']}")
    print(f"  body: {json.dumps(body, sort_keys=True)}")
    print("  send_request: false")


def build_parser() -> argparse.ArgumentParser:
    default_profile = get_default_instrument_profile()
    measurement_choices = ", ".join(
        format_measurement_type(value) for value in _supported_measurement_types(default_profile)
    )
    parser = KeysightArgumentParser(
        prog="keysight-logger",
        formatter_class=KeysightHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"keysight-logger {get_cli_version()}",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    list_resources = sub.add_parser(
        "list-resources",
        formatter_class=KeysightHelpFormatter,
    )
    list_resources.add_argument(
        "--verify",
        action="store_true",
        help="open each resource and query *IDN? to mark live vs stale",
    )
    list_resources.add_argument(
        "--live-only",
        action="store_true",
        help="verify resources and print only live resources",
    )
    list_resources.add_argument(
        "--dry-run",
        action="store_true",
        help="print the discovery contract without touching VISA",
    )
    list_resources.add_argument(
        "--format",
        dest="output_format",
        choices=["text", "json"],
        default="text",
        help="output format for discovered resources; default: text",
    )
    list_resources.add_argument("--json", action="store_true", help="alias for --format json")

    start = sub.add_parser(
        "start-trigger-record",
        formatter_class=KeysightHelpFormatter,
        epilog=_start_help_epilog(default_profile),
    )
    start.add_argument("--resource", required=True, help="VISA resource string")
    start.add_argument(
        "--csv",
        default=None,
        help="CSV output path; default: data/YYYY-MM-DD-HH-MM-SS.csv in UTC+8",
    )
    start.add_argument(
        "--status-format",
        choices=["text", "jsonl"],
        default="text",
        help="status output format for start-trigger-record; default: text",
    )
    start.add_argument("--json", action="store_true", help="alias for --status-format jsonl")
    start.add_argument("--dry-run", action="store_true", help="validate and print the execution plan")
    start.add_argument("--simulate", action="store_true", help="run against a deterministic simulator")
    start.add_argument(
        "--timeout-ms",
        type=int,
        default=5000,
        help="VISA timeout in ms; supported range 100-600000",
    )
    start.add_argument(
        "--trigger-timeout-ms",
        type=int,
        default=10000,
        help="external/custom trigger wait timeout in ms; supported range 500-600000",
    )
    start.add_argument(
        "--sw-trigger-port",
        type=int,
        default=8765,
        help="software trigger server port; use 0 for auto, or 1024-65535",
    )
    start.add_argument(
        "--sw-min-interval-ms",
        type=int,
        default=0,
        help="software trigger throttle; 0 disables, otherwise 50-600000 ms",
    )
    start.add_argument(
        "--sw-queue-max",
        type=int,
        default=0,
        help="software trigger queue depth; 0 uses the default safety cap, max 10000",
    )
    start.add_argument(
        "--trigger-mode",
        choices=[
            "software",
            "external",
            "immediate",
            "immediate-custom",
            "software-custom",
            "external-custom",
        ],
        default=None,
        help="single acquisition trigger mode; default: software",
    )
    start.add_argument(
        "--max-samples",
        type=int,
        default=None,
        help="stop automatically after N successful samples; range 1-1000000, simple modes only",
    )
    start.add_argument(
        "--trigger-count",
        type=int,
        default=None,
        help="instrument trigger count; range 1-1000000, required with custom trigger modes",
    )
    start.add_argument(
        "--sample-count",
        type=int,
        default=None,
        help="instrument sample count per trigger; range 1-1000000, required with custom modes",
    )
    start.add_argument(
        "--timer-interval-s",
        type=float,
        default=None,
        help="software timer interval in seconds; range 0.5-86400, software mode only",
    )
    start.add_argument(
        "--buffer-drain-size",
        type=int,
        default=None,
        help="readings removed per buffer drain; range 1-10000, custom modes only",
    )
    start.add_argument(
        "--allow-buffer-overflow-risk",
        action="store_true",
        help=(
            "allow custom modes to request more readings than "
            f"{default_profile.model} reading memory"
        ),
    )
    start.add_argument(
        "--hw-trigger-slope",
        choices=["pos", "neg"],
        default="neg",
        help="hardware trigger edge polarity (default: neg)",
    )
    start.add_argument(
        "--hw-trigger-delay-s",
        type=float,
        default=0.0,
        help="hardware trigger delay in seconds; supported range 0-3600",
    )
    start.add_argument(
        "--measurement",
        default="current-dc",
        help=f"measurement type; one of: {measurement_choices}",
    )
    start.add_argument(
        "--nplc",
        type=float,
        default=1.0,
        help="NPLC for DC/resistance: 0.02, 0.2, 1, 10, 100; AC supports only neutral 1.0",
    )
    start.add_argument(
        "--auto-zero",
        type=parse_auto_zero,
        default=True,
        help="Auto Zero for supported measurements: on, off, or once",
    )
    start.add_argument("--auto-range", type=parse_on_off, default=True)
    start.add_argument(
        "--range",
        dest="measurement_range",
        type=float,
        default=None,
        help=(
            "manual measurement range; amps for current, volts for voltage, "
            "ohms for resistance"
        ),
    )
    start.add_argument(
        "--current-range",
        type=float,
        default=None,
        help="compatibility alias for --range with --measurement current-dc",
    )
    start.add_argument(
        "--ac-bandwidth-hz",
        type=float,
        default=None,
        help="AC bandwidth for current-ac or voltage-ac: 3, 20, or 200 Hz",
    )
    start.add_argument(
        "--current-terminal",
        type=int,
        choices=[3, 10],
        default=None,
        help="current input terminal for current measurements: 3 or 10",
    )
    start.add_argument(
        "--dcv-input-impedance",
        type=parse_dcv_input_impedance,
        default="default",
        help=(
            "DC voltage input impedance: default leaves instrument setting unchanged, "
            "10m forces 10 MOhm, auto enables instrument Auto/HighZ behavior"
        ),
    )
    start.add_argument(
        "--vm-comp-slope",
        choices=["pos", "neg"],
        default=None,
        help="VM Comp rear-panel output pulse slope; omit to leave unchanged",
    )

    trig = sub.add_parser("soft-trigger", formatter_class=KeysightHelpFormatter)
    trig.add_argument("--port", type=int, default=8765, help="server port; range 1-65535")
    trig.add_argument("--meta", default="{}", help='JSON metadata, e.g. {"batch":"A"}')
    trig.add_argument(
        "--format",
        dest="output_format",
        choices=["text", "json"],
        default="text",
        help="output format for the response; default: text",
    )
    trig.add_argument("--json", action="store_true", help="alias for --format json")
    trig.add_argument("--dry-run", action="store_true", help="preview the request without sending it")
    stop = sub.add_parser("soft-stop", formatter_class=KeysightHelpFormatter)
    stop.add_argument("--port", type=int, default=8765, help="server port; range 1-65535")
    stop.add_argument(
        "--format",
        dest="output_format",
        choices=["text", "json"],
        default="text",
        help="output format for the response; default: text",
    )
    stop.add_argument("--json", action="store_true", help="alias for --format json")
    stop.add_argument("--dry-run", action="store_true", help="preview the request without sending it")

    return parser


def cmd_list_resources(
    verify: bool = False,
    live_only: bool = False,
    output_format: str = "text",
    dry_run: bool = False,
    print_fn=print,  # noqa: ANN001
    resource_manager_factory=None,  # noqa: ANN001
) -> int:
    if output_format not in {"text", "json"}:
        raise ValueError("output_format must be 'text' or 'json'")

    effective_verify = verify or live_only
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
    for resource in VisaInstrument.list_resources(resource_manager_factory=resource_manager_factory):
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
        payload = {"resources": resources, "verify": effective_verify}
        if live_only:
            payload["live_only"] = True
        print_fn(
            json.dumps(
                payload,
                sort_keys=True,
            )
        )
    return 0


def cmd_soft_trigger(port: int, meta: str, output_format: str = "text", dry_run: bool = False) -> int:
    try:
        payload = json.dumps(json.loads(meta)).encode("utf-8")
    except json.JSONDecodeError:
        if output_format == "json":
            print(
                json.dumps(
                    {
                        "event": "error",
                        "exit_code": 2,
                        "message": "meta must be valid JSON",
                        "schema_version": CLI_EVENT_SCHEMA_VERSION,
                        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    },
                    sort_keys=True,
                )
            )
        else:
            print("meta must be valid JSON", file=sys.stderr)
        return 2
    if dry_run:
        _emit_client_dry_run("soft-trigger", port, json.loads(meta), output_format)
        return 0
    req = request.Request(
        f"http://127.0.0.1:{port}/trigger",
        method="POST",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with request.urlopen(req, timeout=3) as response:
            if output_format == "json":
                print(
                    json.dumps(
                        {
                            "event": "soft-trigger",
                            "http_status": response.status,
                            "message": "trigger accepted",
                            "schema_version": CLI_EVENT_SCHEMA_VERSION,
                            "status": "accepted",
                            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                        },
                        sort_keys=True,
                    )
                )
            else:
                print(f"trigger accepted: {response.status}")
    except URLError as exc:
        if output_format == "json":
            print(
                json.dumps(
                    {
                        "event": "error",
                        "exit_code": 3,
                        "message": f"trigger request failed: {exc}",
                        "schema_version": CLI_EVENT_SCHEMA_VERSION,
                        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    },
                    sort_keys=True,
                )
            )
        else:
            print(f"trigger request failed: {exc}", file=sys.stderr)
        return 3
    return 0


def cmd_soft_stop(port: int, output_format: str = "text", dry_run: bool = False) -> int:
    if dry_run:
        _emit_client_dry_run("soft-stop", port, {}, output_format)
        return 0
    req = request.Request(
        f"http://127.0.0.1:{port}/stop",
        method="POST",
        data=b"{}",
        headers={"Content-Type": "application/json"},
    )
    try:
        with request.urlopen(req, timeout=3) as response:
            if output_format == "json":
                print(
                    json.dumps(
                        {
                            "event": "soft-stop",
                            "http_status": response.status,
                            "message": "stop accepted",
                            "schema_version": CLI_EVENT_SCHEMA_VERSION,
                            "status": "accepted",
                            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                        },
                        sort_keys=True,
                    )
                )
            else:
                print(f"stop accepted: {response.status}")
    except URLError as exc:
        reason = getattr(exc, "reason", None)
        winerror = getattr(reason, "winerror", None)
        errno = getattr(reason, "errno", None)
        if winerror == 10061 or errno == 10061:
            if output_format == "json":
                print(
                    json.dumps(
                        {
                            "event": "soft-stop",
                            "message": "already stopped (endpoint not listening)",
                            "schema_version": CLI_EVENT_SCHEMA_VERSION,
                            "status": "already_stopped",
                            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                        },
                        sort_keys=True,
                    )
                )
            else:
                print("already stopped (endpoint not listening)")
            return 0
        if output_format == "json":
            print(
                json.dumps(
                    {
                        "event": "error",
                        "exit_code": 3,
                        "message": f"stop request failed: {exc}",
                        "schema_version": CLI_EVENT_SCHEMA_VERSION,
                        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    },
                    sort_keys=True,
                )
            )
        else:
            print(f"stop request failed: {exc}", file=sys.stderr)
        return 3
    return 0


def cmd_start(args: argparse.Namespace) -> int:
    instrument_profile = get_default_instrument_profile()
    emitter = CliEventEmitter(print_fn=print, output_format=args.status_format)
    request_model: StartRequest
    try:
        request_model = _start_request_from_args(args)
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
        )
    if args.command == "soft-trigger":
        try:
            validate_client_port(args.port)
        except ValueError as exc:
            if args.output_format == "json":
                print(
                    json.dumps(
                        {
                            "event": "error",
                            "exit_code": 2,
                            "message": str(exc),
                            "schema_version": CLI_EVENT_SCHEMA_VERSION,
                            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                        },
                        sort_keys=True,
                    )
                )
            else:
                print(str(exc), file=sys.stderr)
            return 2
        return cmd_soft_trigger(args.port, args.meta, args.output_format, args.dry_run)
    if args.command == "soft-stop":
        try:
            validate_client_port(args.port)
        except ValueError as exc:
            if args.output_format == "json":
                print(
                    json.dumps(
                        {
                            "event": "error",
                            "exit_code": 2,
                            "message": str(exc),
                            "schema_version": CLI_EVENT_SCHEMA_VERSION,
                            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                        },
                        sort_keys=True,
                    )
                )
            else:
                print(str(exc), file=sys.stderr)
            return 2
        return cmd_soft_stop(args.port, args.output_format, args.dry_run)
    if args.command == "start-trigger-record":
        return cmd_start(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
