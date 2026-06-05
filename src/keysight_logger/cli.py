from __future__ import annotations

import argparse
import ctypes
import json
import signal
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib import request
from urllib.error import URLError

from .acquisition import TriggerAcquisitionEngine
from .instrument import InstrumentConfig, InstrumentError, VisaInstrument
from .measurement import (
    create_measurement_plugin,
    format_measurement_type,
    get_measurement_definition,
    normalize_measurement_type,
    registered_measurement_types,
)
from .models import AcquisitionConfig, InstrumentProfile, get_default_instrument_profile
from .simulator import SimulatedVisaInstrument
from .storage import CsvWriter, UTC_PLUS_8
from .trigger import HardwareTriggerAdapter, SoftwareTriggerAdapter, TriggerRouter


TIMER_INTERVAL_S_RANGE = (0.5, 86400.0)
TRIGGER_TIMEOUT_MS_RANGE = (500, 600000)
TIMEOUT_MS_RANGE = (100, 600000)
TRIGGER_COUNT_RANGE = (1, 1000000)
SAMPLE_COUNT_RANGE = (1, 1000000)
BUFFER_DRAIN_SIZE_RANGE = (1, 10000)
MAX_SAMPLES_RANGE = (1, 1000000)
SW_TRIGGER_PORT_RANGE = (0, 65535)
CLIENT_PORT_RANGE = (1, 65535)
SW_MIN_INTERVAL_MS_RANGE = (0, 600000)
SW_QUEUE_MAX_RANGE = (0, 10000)
HW_TRIGGER_DELAY_S_RANGE = (0.0, 3600.0)
NEUTRAL_AC_NPLC = 1.0
CLI_EVENT_SCHEMA_VERSION = 1


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


class StopController:
    def __init__(self, stop_engine, print_fn=print):  # noqa: ANN001
        self.stop = False
        self.interrupt_count = 0
        self.force = False
        self._stop_engine = stop_engine
        self._print = print_fn
        self._lock = threading.Lock()

    def request_stop(self, force: bool = False) -> None:
        with self._lock:
            self.stop = True
            if force:
                self.force = True
                message = "second interrupt received, forcing shutdown..."
            else:
                message = "interrupt received, stopping gracefully (press Ctrl+C again to force)..."
        self._stop_engine()
        self._print(message)

    def request_http_stop(self) -> None:
        with self._lock:
            self.stop = True
        self._stop_engine()

    def request_signal_stop(self) -> None:
        with self._lock:
            self.interrupt_count += 1
            force = self.interrupt_count >= 2
        self.request_stop(force=force)


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


def parse_on_off(value: str) -> bool:
    lower = str(value).strip().lower()
    if lower == "on":
        return True
    if lower == "off":
        return False
    raise argparse.ArgumentTypeError("value must be 'on' or 'off'")


def parse_dcv_input_impedance(value: str) -> str:
    normalized = str(value).strip().lower()
    if normalized in {"default", "10m", "auto"}:
        return normalized
    raise argparse.ArgumentTypeError("value must be 'default', '10m', or 'auto'")


def resolve_csv_path(csv_path: str | None, now: datetime | None = None) -> Path:
    if csv_path is not None:
        return Path(csv_path)
    effective_now = now or datetime.now(UTC_PLUS_8)
    if effective_now.tzinfo is None:
        effective_now = effective_now.replace(tzinfo=UTC_PLUS_8)
    timestamp = effective_now.astimezone(UTC_PLUS_8).strftime("%Y-%m-%d-%H-%M-%S")
    return Path("data") / f"{timestamp}.csv"


def resolve_measurement_range(args: argparse.Namespace) -> float | None:
    if args.measurement_range is not None and args.current_range is not None:
        raise ValueError("--range and --current-range cannot be used together")
    if args.measurement_range is not None:
        return args.measurement_range
    return args.current_range


def _format_number(value: float | int) -> str:
    numeric = float(value)
    if numeric.is_integer():
        return str(int(numeric))
    return f"{numeric:g}"


def _format_values(values: tuple[float, ...]) -> str:
    return ", ".join(_format_number(value) for value in values)


def _format_range_options(options) -> str:  # noqa: ANN001
    return _format_values(tuple(value for _label, value in options.range_options))


def _range_unit(definition) -> str:  # noqa: ANN001
    if definition.unit == "A":
        return "A"
    if definition.unit == "V":
        return "V"
    return "Ohm"


def _value_in_options(value: float, options: tuple[float, ...]) -> bool:
    return any(abs(float(value) - float(option)) <= 1e-12 for option in options)


def _supported_measurement_types(profile: InstrumentProfile) -> tuple[str, ...]:
    registered_measurements = set(registered_measurement_types())
    return tuple(value for value in profile.supported_measurement_types if value in registered_measurements)


def _validate_int_range(name: str, value: int, minimum: int, maximum: int, detail: str) -> None:
    if value < minimum or value > maximum:
        raise ValueError(
            f"{name} {value} is outside the {detail} range {minimum}-{maximum}. "
            f"Use a value from {minimum} to {maximum}."
        )


def _validate_float_range(
    name: str,
    value: float,
    minimum: float,
    maximum: float,
    unit: str,
) -> None:
    if value < minimum or value > maximum:
        raise ValueError(
            f"{name} {_format_number(value)} is outside the supported range "
            f"{_format_number(minimum)}-{_format_number(maximum)} {unit}. "
            f"Use a value from {_format_number(minimum)} to {_format_number(maximum)} {unit}."
        )


def _start_help_epilog(profile: InstrumentProfile | None = None) -> str:
    effective_profile = profile or get_default_instrument_profile()
    measurement_names = [
        format_measurement_type(value) for value in _supported_measurement_types(effective_profile)
    ]
    range_lines = []
    for measurement_name in measurement_names:
        definition = get_measurement_definition(measurement_name)
        options = effective_profile.get_measurement_options(measurement_name)
        range_lines.append(
            f"  {definition.cli_name}: {_format_range_options(options)} {definition.unit}"
        )
    return (
        "Limits:\n"
        f"  measurement choices: {', '.join(measurement_names)}\n"
        "  NPLC choices for DC/resistance: 0.02, 0.2, 1, 10, 100\n"
        "  AC current/voltage do not support NPLC SCPI; omit --nplc or use 1.0\n"
        "  range choices by measurement:\n"
        + "\n".join(range_lines)
        + "\n"
        "  --timer-interval-s: 0.5-86400 s, software mode only\n"
        "  --trigger-timeout-ms: 500-600000 ms\n"
        "  --timeout-ms: 100-600000 ms\n"
        "  --trigger-count/--sample-count: 1-1000000, custom modes only\n"
        "  --buffer-drain-size: 1-10000, custom modes only\n"
        "  --max-samples: 1-1000000, simple modes only\n"
        "  --sw-trigger-port: 0 or 1024-65535; 0 lets the server choose\n"
        "  --sw-min-interval-ms: 0 or 50-600000 ms\n"
        "  --sw-queue-max: 0-10000\n"
        "  --hw-trigger-delay-s: 0-3600 s\n"
        "  custom trigger_count * sample_count > 10000 requires --allow-buffer-overflow-risk"
    )


class _PlanRecorder:
    def __init__(self) -> None:
        self.commands: list[str] = []

    def write(self, command: str) -> None:
        self.commands.append(command)

    def query(self, command: str) -> str:
        self.commands.append(f"query:{command}")
        return "1.23"

    def query_ascii_float(self, command: str) -> float:
        self.commands.append(command)
        return 1.23

    def set_timeout_ms(self, timeout_ms: int) -> None:  # noqa: ARG002
        return None

    @property
    def resource_id(self) -> str:
        return "<dry-run>"


@dataclass
class StartCommandPlan:
    trigger_mode: str
    measurement_type: str
    measurement_cli_name: str
    measurement_unit: str
    csv_path: str
    resource: str
    simulate: bool
    dry_run: bool
    status_format: str
    scpi_commands: list[str]
    read_path: str
    cleanup_steps: list[str]
    notes: list[str]


class CliEventEmitter:
    def __init__(self, print_fn=print, output_format: str = "text") -> None:  # noqa: ANN001
        self._print = print_fn
        self._output_format = output_format

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

    def sample(self, sample, captured: int) -> None:  # noqa: ANN001
        if self._output_format == "jsonl":
            payload = {
                "captured": captured,
                "event": "sample",
                "measurement_type": sample.measurement_type,
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
            self._emit_json(payload)

    def summary(self, captured: int, errors: int, fatal_error: str | None = None) -> None:
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
            self._emit_json(payload)
            return
        self._print(f"captured={captured} errors={errors}")

    def line(self, message: str) -> None:
        if self._output_format == "jsonl":
            self._emit_json(
                {
                    "event": "message",
                    "message": message,
                    "schema_version": CLI_EVENT_SCHEMA_VERSION,
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                }
            )
            return
        self._print(message)

    def error(self, message: str, rc: int = 3) -> None:
        if self._output_format == "jsonl":
            self._emit_json(
                {
                    "event": "error",
                    "message": message,
                    "schema_version": CLI_EVENT_SCHEMA_VERSION,
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "exit_code": rc,
                }
            )
            return
        self._print(message, file=sys.stderr)


def _start_plan(args: argparse.Namespace, trigger_mode: str, profile: InstrumentProfile, buffer_warnings: list[str] | None = None) -> StartCommandPlan:
    measurement_type = normalize_measurement_type(args.measurement)
    measurement_def = get_measurement_definition(measurement_type)
    csv_path = str(resolve_csv_path(args.csv))
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
        measurement_range=resolve_measurement_range(args),
        current_range=args.current_range,
        dcv_input_impedance=args.dcv_input_impedance,
        hw_trigger_delay_s=args.hw_trigger_delay_s,
        vm_comp_slope=args.vm_comp_slope,
    )
    measurement = create_measurement_plugin(measurement_type)
    recorder = _PlanRecorder()
    measurement.configure(recorder, config)
    if trigger_mode == "external":
        HardwareTriggerAdapter(recorder).configure_external_trigger(
            slope=args.hw_trigger_slope,
            delay_s=args.hw_trigger_delay_s,
        )
    elif trigger_mode == "immediate-custom":
        measurement.configure_immediate_custom(
            recorder,
            config,
            trigger_count=args.trigger_count,
            sample_count=args.sample_count,
        )
        measurement.start_buffered_capture(recorder)
    elif trigger_mode == "software-custom":
        measurement.configure_software_custom(
            recorder,
            config,
            trigger_count=args.trigger_count,
            sample_count=args.sample_count,
        )
        measurement.start_buffered_capture(recorder)
    elif trigger_mode == "external-custom":
        measurement.configure_external_custom(
            recorder,
            config,
            trigger_count=args.trigger_count,
            sample_count=args.sample_count,
            slope=args.hw_trigger_slope,
            delay_s=args.hw_trigger_delay_s,
        )
        measurement.start_buffered_capture(recorder)
    scpi_commands = recorder.commands
    if trigger_mode.endswith("-custom"):
        read_path = "DATA:POINts? / DATA:REMove?"
    elif trigger_mode == "external":
        read_path = "FETC?"
    else:
        read_path = "READ?"
    cleanup_steps = [
        "wait for worker",
        "release_to_local",
        "close",
        "cleanup_release_to_local",
        "stop_http_server",
    ]
    notes: list[str] = []
    if buffer_warnings:
        notes.extend(buffer_warnings)
    if trigger_mode.endswith("-custom"):
        notes.append("buffered drain uses DATA:POINts? and DATA:REMove?")
    if trigger_mode == "external":
        notes.append("hardware trigger uses INIT + status-byte polling before FETC?")
    if trigger_mode == "software-custom":
        notes.append("software-custom uses BUS trigger plus *TRG")
    if trigger_mode == "immediate-custom":
        notes.append("immediate-custom uses IMM trigger source")
    if args.simulate:
        notes.append("simulate uses deterministic fake instrument values")
    return StartCommandPlan(
        trigger_mode=trigger_mode,
        measurement_type=measurement_type,
        measurement_cli_name=measurement_def.cli_name,
        measurement_unit=measurement_def.unit,
        csv_path=csv_path,
        resource=args.resource,
        simulate=args.simulate,
        dry_run=args.dry_run,
        status_format=args.status_format,
        scpi_commands=scpi_commands,
        read_path=read_path,
        cleanup_steps=cleanup_steps,
        notes=notes,
    )


def _emit_start_plan(plan: StartCommandPlan, emitter: CliEventEmitter) -> None:
    if plan.status_format == "jsonl":
        emitter._emit_json(
            {
                "event": "dry_run",
                "schema_version": CLI_EVENT_SCHEMA_VERSION,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "trigger_mode": plan.trigger_mode,
                "measurement_type": plan.measurement_type,
                "measurement_cli_name": plan.measurement_cli_name,
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
    emitter.line(f"  measurement: {plan.measurement_cli_name} ({plan.measurement_unit})")
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
    start.add_argument("--enable-hw-trigger", action="store_true")
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
    start.add_argument("--auto-zero", type=parse_on_off, default=True)
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
    print_fn=print,  # noqa: ANN001
) -> int:
    if output_format not in {"text", "json"}:
        raise ValueError("output_format must be 'text' or 'json'")

    effective_verify = verify or live_only
    resources = []
    text_rows = 0
    for resource in VisaInstrument.list_resources():
        if not effective_verify:
            if output_format == "text":
                print_fn(resource)
                text_rows += 1
            else:
                resources.append({"resource": resource})
            continue
        ok, detail = VisaInstrument.verify_resource(resource)
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


def validate_client_port(port: int, command_name: str) -> None:
    if port < CLIENT_PORT_RANGE[0] or port > CLIENT_PORT_RANGE[1]:
        raise ValueError(
            f"--port {port} is outside the supported range 1-65535 for {command_name}. "
            "Use a TCP port from 1 to 65535."
        )


def resolve_trigger_mode(args: argparse.Namespace) -> str:
    trigger_mode = args.trigger_mode or "software"
    if args.enable_hw_trigger:
        if args.trigger_mode is not None and args.trigger_mode != "external":
            raise ValueError("--enable-hw-trigger conflicts with --trigger-mode; use external")
        trigger_mode = "external"
    return trigger_mode


def validate_start_args(
    args: argparse.Namespace,
    trigger_mode: str,
    instrument_profile: InstrumentProfile | None = None,
) -> None:
    custom_mode = trigger_mode.endswith("-custom")
    profile = instrument_profile or get_default_instrument_profile()
    measurement_type = normalize_measurement_type(args.measurement)
    supported_measurements = _supported_measurement_types(profile)
    if measurement_type not in supported_measurements:
        choices = ", ".join(format_measurement_type(value) for value in supported_measurements)
        raise ValueError(f"--measurement must be one of: {choices}")
    definition = get_measurement_definition(measurement_type)
    options = profile.get_measurement_options(measurement_type)
    if not definition.accepts_current_range_alias and args.current_range is not None:
        raise ValueError("--current-range can only be used with --measurement current-dc")
    if args.dcv_input_impedance != "default" and measurement_type != "voltage_dc":
        raise ValueError("--dcv-input-impedance can only be used with --measurement voltage-dc")
    if args.measurement_range is not None and args.current_range is not None:
        raise ValueError("--range and --current-range cannot be used together")
    _validate_int_range("--timeout-ms", args.timeout_ms, *TIMEOUT_MS_RANGE, "supported")
    _validate_int_range(
        "--trigger-timeout-ms",
        args.trigger_timeout_ms,
        *TRIGGER_TIMEOUT_MS_RANGE,
        "supported",
    )
    if args.sw_trigger_port != 0 and (
        args.sw_trigger_port < 1024 or args.sw_trigger_port > SW_TRIGGER_PORT_RANGE[1]
    ):
        raise ValueError(
            f"--sw-trigger-port {args.sw_trigger_port} is outside the supported values. "
            "Use 0 to let the server choose a port, or use a port from 1024 to 65535."
        )
    if args.sw_min_interval_ms != 0 and (
        args.sw_min_interval_ms < 50 or args.sw_min_interval_ms > SW_MIN_INTERVAL_MS_RANGE[1]
    ):
        raise ValueError(
            f"--sw-min-interval-ms {args.sw_min_interval_ms} is outside the supported values. "
            "Use 0 to disable throttling, or use a value from 50 to 600000 ms."
        )
    _validate_int_range("--sw-queue-max", args.sw_queue_max, *SW_QUEUE_MAX_RANGE, "supported")
    if args.measurement_range is not None:
        allowed_ranges = tuple(value for _label, value in options.range_options)
        if not _value_in_options(args.measurement_range, allowed_ranges):
            raise ValueError(
                f"--range {_format_number(args.measurement_range)} is not valid for "
                f"--measurement {definition.cli_name}. Allowed ranges in "
                f"{_range_unit(definition)}: {_format_range_options(options)}. "
                "Use one of the listed range values or omit --range with --auto-range on."
            )
    if args.current_range is not None:
        allowed_ranges = tuple(value for _label, value in options.range_options)
        if not _value_in_options(args.current_range, allowed_ranges):
            raise ValueError(
                f"--current-range {_format_number(args.current_range)} is not valid for "
                f"--measurement {definition.cli_name}. Allowed ranges in "
                f"{_range_unit(definition)}: {_format_range_options(options)}. "
                "Use one of the listed current range values."
            )
    measurement_range = resolve_measurement_range(args)
    if options.nplc_options:
        if not _value_in_options(args.nplc, options.nplc_options):
            raise ValueError(
                f"--nplc {_format_number(args.nplc)} is not valid for "
                f"--measurement {definition.cli_name}. Allowed NPLC values: "
                f"{_format_values(options.nplc_options)}. Use one of the listed values."
            )
    elif args.nplc != NEUTRAL_AC_NPLC:
        raise ValueError(
            f"--nplc {_format_number(args.nplc)} is not valid for "
            f"--measurement {definition.cli_name}. AC measurements do not support NPLC SCPI. "
            "Omit --nplc or use the neutral default value 1.0."
        )
    _validate_float_range(
        "--hw-trigger-delay-s",
        args.hw_trigger_delay_s,
        *HW_TRIGGER_DELAY_S_RANGE,
        "s",
    )
    if not args.auto_range and measurement_range is None and measurement_type == "current_dc":
        raise ValueError("--range or --current-range is required when --auto-range off")
    if not args.auto_range and measurement_range is None:
        raise ValueError("--range is required when --auto-range off")
    if args.max_samples is not None:
        _validate_int_range("--max-samples", args.max_samples, *MAX_SAMPLES_RANGE, "supported")
    if args.trigger_count is not None:
        _validate_int_range(
            "--trigger-count",
            args.trigger_count,
            *TRIGGER_COUNT_RANGE,
            "34461A supported",
        )
    if args.sample_count is not None:
        _validate_int_range(
            "--sample-count",
            args.sample_count,
            *SAMPLE_COUNT_RANGE,
            "34461A supported",
        )
    if args.timer_interval_s is not None:
        if args.timer_interval_s < TIMER_INTERVAL_S_RANGE[0]:
            raise ValueError(
                f"--timer-interval-s {_format_number(args.timer_interval_s)} is below "
                f"the supported minimum {_format_number(TIMER_INTERVAL_S_RANGE[0])} s. "
                "This is a PC-side timer and is not reliable below 0.5 s."
            )
        if args.timer_interval_s > TIMER_INTERVAL_S_RANGE[1]:
            raise ValueError(
                f"--timer-interval-s {_format_number(args.timer_interval_s)} is outside "
                "the supported range 0.5-86400 s. Use a value from 0.5 to 86400 s."
            )
        if trigger_mode != "software":
            raise ValueError("--timer-interval-s requires --trigger-mode software")
    if args.buffer_drain_size is not None:
        max_buffer_drain_size = min(BUFFER_DRAIN_SIZE_RANGE[1], profile.reading_memory_limit)
        _validate_int_range(
            "--buffer-drain-size",
            args.buffer_drain_size,
            BUFFER_DRAIN_SIZE_RANGE[0],
            max_buffer_drain_size,
            f"{profile.model} reading-memory",
        )
        if not custom_mode:
            raise ValueError("--buffer-drain-size requires a custom trigger mode")
    if args.allow_buffer_overflow_risk and not custom_mode:
        raise ValueError("--allow-buffer-overflow-risk requires a custom trigger mode")
    if custom_mode:
        if args.max_samples is not None:
            raise ValueError("--max-samples cannot be used with custom trigger modes")
        if args.trigger_count is None:
            raise ValueError("--trigger-count is required with custom trigger modes")
        if args.sample_count is None:
            raise ValueError("--sample-count is required with custom trigger modes")
        memory_limit = profile.reading_memory_limit
        expected_readings = args.trigger_count * args.sample_count
        if expected_readings > memory_limit and not args.allow_buffer_overflow_risk:
            raise ValueError(
                f"custom mode expected readings {expected_readings} exceed "
                f"{profile.model} reading memory {memory_limit}; "
                "add --allow-buffer-overflow-risk to proceed."
            )
    else:
        if args.trigger_count is not None:
            raise ValueError("--trigger-count requires a custom trigger mode")
        if args.sample_count is not None:
            raise ValueError("--sample-count requires a custom trigger mode")
        if getattr(args, "simulate", False) and args.max_samples is None:
            raise ValueError("--simulate requires --max-samples with simple trigger modes")


def print_buffer_overflow_warnings(
    args: argparse.Namespace,
    trigger_mode: str,
    instrument_profile: InstrumentProfile | None = None,
    emit_fn=None,  # noqa: ANN001
) -> list[str]:
    warnings: list[str] = []
    if emit_fn is None:
        emit_fn = print
    profile = instrument_profile or get_default_instrument_profile()
    if not trigger_mode.endswith("-custom") or not args.allow_buffer_overflow_risk:
        return []
    if args.trigger_count is None or args.sample_count is None:
        return []
    memory_limit = profile.reading_memory_limit
    expected_readings = args.trigger_count * args.sample_count
    if expected_readings <= memory_limit:
        return []
    model = profile.model
    msg1 = f"WARNING: requested readings exceed {model} reading memory."
    msg2 = f"WARNING: requested={expected_readings}, memory_limit={memory_limit}."
    msg3 = "WARNING: this depends on DATA:REMove? draining faster than acquisition fills memory."
    msg4 = "WARNING: data loss, incomplete rows, or SCPI errors are possible."
    msg5 = "WARNING: validate with low counts first and inspect row count/errors."
    for msg in [msg1, msg2, msg3, msg4, msg5]:
        emit_fn(msg)
        warnings.append(msg)
    return warnings


def cmd_start(args: argparse.Namespace) -> int:
    instrument_profile = get_default_instrument_profile()
    emitter = CliEventEmitter(print_fn=print, output_format=args.status_format)
    try:
        trigger_mode = resolve_trigger_mode(args)
        if args.dry_run and args.simulate:
            raise ValueError("--dry-run and --simulate cannot be used together")
        validate_start_args(args, trigger_mode, instrument_profile=instrument_profile)
    except ValueError as exc:
        emitter.error(str(exc), rc=2)
        return 2
    if args.dry_run:
        warnings = print_buffer_overflow_warnings(
            args,
            trigger_mode,
            instrument_profile=instrument_profile,
            emit_fn=lambda _message: None,
        )
    else:
        warnings = print_buffer_overflow_warnings(
            args,
            trigger_mode,
            instrument_profile=instrument_profile,
            emit_fn=emitter.status if args.status_format == "jsonl" else emitter.line,
        )

    plan = _start_plan(
        args,
        trigger_mode,
        instrument_profile,
        buffer_warnings=warnings if args.dry_run else None,
    )
    if args.dry_run:
        _emit_start_plan(plan, emitter)
        return 0

    measurement_type = plan.measurement_type
    measurement_range = resolve_measurement_range(args)
    csv_path = Path(plan.csv_path)
    if args.csv is None:
        emitter.line(f"csv output path: {csv_path}")
    iconfig = InstrumentConfig(resource_string=args.resource, timeout_ms=args.timeout_ms)
    aconfig = AcquisitionConfig(
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
    instrument = (
        SimulatedVisaInstrument(iconfig, measurement_type=measurement_type)
        if args.simulate
        else VisaInstrument(iconfig)
    )
    router = TriggerRouter(max_pending_events=args.sw_queue_max)
    storage = CsvWriter(csv_path)
    measurement = create_measurement_plugin(measurement_type)
    engine = TriggerAcquisitionEngine(
        instrument=instrument,
        measurement=measurement,
        storage=storage,
        config=aconfig,
        router=router,
        status_cb=lambda m: emitter.status(m),
        sample_cb=lambda sample, captured: emitter.sample(sample, captured),
        instrument_profile=instrument_profile,
    )

    stop_controller = StopController(engine.stop)

    def worker_status() -> dict[str, object]:
        return {
            "status": "stopping" if stop_controller.stop else "running",
            "captured": engine.stats.captured,
            "errors": engine.stats.errors,
            "fatal_error": engine.fatal_error,
        }

    server = SoftwareTriggerAdapter(
        router,
        port=args.sw_trigger_port,
        min_interval_ms=args.sw_min_interval_ms,
        queue_max=args.sw_queue_max,
        stop_cb=stop_controller.request_http_stop,
        status_provider=worker_status,
    )

    def handle_stop_signal(signum, frame):  # noqa: ARG001
        stop_controller.request_signal_stop()

    previous_signal_handlers = []
    previous_signal_handlers.append((signal.SIGINT, signal.signal(signal.SIGINT, handle_stop_signal)))
    if hasattr(signal, "SIGTERM"):
        previous_signal_handlers.append(
            (signal.SIGTERM, signal.signal(signal.SIGTERM, handle_stop_signal))
        )
    if hasattr(signal, "SIGBREAK"):
        previous_signal_handlers.append(
            (signal.SIGBREAK, signal.signal(signal.SIGBREAK, handle_stop_signal))
        )
    windows_console_stop_handler = WindowsConsoleStopHandler(stop_controller)
    keyboard_stop_poller = WindowsKeyboardStopPoller()

    worker: threading.Thread | None = None
    connected = False
    try:
        try:
            instrument.connect()
            connected = True
        except InstrumentError as exc:
            emitter.error(f"error: {exc}", rc=3)
            return 3
        if windows_console_stop_handler.install():
            emitter.line(
                "windows console stop handler: installed "
                f"processed_input={windows_console_stop_handler.input_mode_configured}"
            )
        elif sys.platform == "win32":
            emitter.error("windows console stop handler: unavailable", rc=3)
        host, port = server.start()
        emitter.line(f"software trigger endpoint: http://{host}:{port}/trigger")
        emitter.line(f"software stop endpoint: http://{host}:{port}/stop")
        emitter.line(f"software status endpoint: http://{host}:{port}/status")
        emitter.line("local stop keys: Ctrl+C, Ctrl+Break, q")
        worker = threading.Thread(
            target=engine.run,
            kwargs={
                "trigger_mode": trigger_mode,
                "hardware_trigger_slope": args.hw_trigger_slope,
            },
            daemon=True,
        )
        worker.start()
        try:
            while worker.is_alive() and not stop_controller.stop:
                if keyboard_stop_poller.poll_stop_requested():
                    stop_controller.request_signal_stop()
                    break
                time.sleep(0.2)
            if not worker.is_alive() and not stop_controller.stop:
                if engine.fatal_error:
                    emitter.error(f"error: {engine.fatal_error}", rc=3)
                else:
                    emitter.line("measurement worker exited before stop was requested")
        except KeyboardInterrupt:
            stop_controller.request_signal_stop()
            while worker.is_alive():
                try:
                    worker.join(timeout=0.2)
                    if not worker.is_alive():
                        break
                except KeyboardInterrupt:
                    stop_controller.request_signal_stop()
                    break
        finally:
            emitter.line("main cleanup starting")
            engine.stop()
            if worker.is_alive():
                join_timeout_s = max(args.trigger_timeout_ms / 1000.0 + 1.0, 2.0)
                emitter.line(f"waiting for measurement worker to stop, timeout_s={join_timeout_s:.1f}")
                worker.join(timeout=join_timeout_s)
            if worker.is_alive() or stop_controller.force:
                emitter.line(f"release_to_local before close: {instrument.release_to_local()}")
                instrument.close()
                worker.join(timeout=2)
        emitter.summary(engine.stats.captured, engine.stats.errors, engine.fatal_error)
        if engine.fatal_error:
            return 3
        return 0
    finally:
        emitter.line("final cleanup starting")
        # Ensure worker exits before final release/close.
        if worker is not None and worker.is_alive():
            emitter.line("waiting worker to fully stop...")
            worker.join(timeout=5)

        # Release instrument control before closing the session.
        if connected:
            rel = instrument.release_to_local()
            emitter.line(f"release_to_local: {rel}")
            # Retry once on transient session instability.
            if "SYST:LOC:failed" in rel:
                time.sleep(1.0)
                rel2 = instrument.release_to_local()
                emitter.line(f"release_to_local retry: {rel2}")
            instrument.close()
            emitter.line(f"cleanup_release_to_local: {instrument.cleanup_release_to_local()}")
        emitter.line("stopping software trigger server")
        server.stop()
        emitter.line("software trigger server stopped")
        windows_console_stop_handler.uninstall()
        for sig, previous_handler in previous_signal_handlers:
            signal.signal(sig, previous_handler)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "list-resources":
        return cmd_list_resources(
            verify=args.verify,
            live_only=args.live_only,
            output_format=args.output_format,
        )
    if args.command == "soft-trigger":
        try:
            validate_client_port(args.port, "soft-trigger")
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
            validate_client_port(args.port, "soft-stop")
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
