from __future__ import annotations

import argparse
import sys

from keysight_logger_core.measurement import format_measurement_type
from keysight_logger_core.models import get_default_instrument_profile
from keysight_logger_core.validation import (
    start_help_epilog as _start_help_epilog,
    supported_measurement_types as _supported_measurement_types,
)


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
    if getattr(args, "command", None) in {
        "list-resources",
        "send-command",
        "stop",
        "status",
        "wait-ready",
    }:
        if not getattr(args, "json", False):
            return
        output_format = _last_option_value(argv, "--format")
        if output_format is not None and output_format != "json":
            parser.error(f"--json conflicts with --format {output_format}")
        args.output_format = "json"


def _add_visa_library_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--visa-library",
        "--backend",
        dest="visa_library",
        default=None,
        help=(
            "optional PyVISA library/backend argument, such as @py. "
            "Default uses the system VISA runtime."
        ),
    )


def build_parser(version_provider) -> argparse.ArgumentParser:
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
        version=f"keysight-logger {version_provider()}",
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
        "--serial-read-termination",
        choices=["CRLF", "LF", "CR", "NONE"],
        default=None,
        help="ASRL verification read termination for list-resources only",
    )
    list_resources.add_argument(
        "--serial-write-termination",
        choices=["CRLF", "LF", "CR", "NONE"],
        default=None,
        help="ASRL verification write termination for list-resources only",
    )
    _add_visa_library_argument(list_resources)
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
        "--model",
        "--instrument-model",
        dest="instrument_model",
        choices=["34460A", "34461A"],
        default=None,
        help="instrument model profile; default: 34461A",
    )
    _add_visa_library_argument(start)
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
            "allow custom modes to request more readings than the selected "
            "profile reading memory"
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
        help=(
            "NPLC for DC/resistance: 0.02, 0.2, 1, 10, 100; "
            "AC/Frequency/Period support only neutral 1.0"
        ),
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
        help=(
            "AC filter bandwidth for current-ac, voltage-ac, frequency, or period: "
            "3, 20, or 200 Hz"
        ),
    )
    start.add_argument(
        "--gate-time-s",
        type=float,
        choices=[0.01, 0.1, 1.0],
        metavar="{0.01,0.1,1}",
        default=None,
        help="Frequency/Period gate time in seconds; default: 0.1",
    )
    start.add_argument(
        "--freq-period-timeout",
        choices=["auto", "1s"],
        default=None,
        help="Frequency timeout behavior; default: auto; unsupported for Period",
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

    send_command = sub.add_parser("send-command", formatter_class=KeysightHelpFormatter)
    send_command.add_argument("--port", type=int, default=8765, help="server port; range 1-65535")
    send_command.add_argument(
        "--timeout-ms",
        type=int,
        default=3000,
        help="HTTP client timeout in ms; supported range 100-600000",
    )
    send_command.add_argument(
        "--command",
        dest="command_name",
        default="software_trigger",
        help="Meters command name; supported: software_trigger",
    )
    send_command.add_argument(
        "--arguments-json",
        default="{}",
        help='JSON command arguments, e.g. {"metadata":{"batch":"A"}}',
    )
    send_command.add_argument("--job-id", default=None, help="optional client-generated job id")
    send_command.add_argument(
        "--format",
        dest="output_format",
        choices=["text", "json"],
        default="text",
        help="output format for the response; default: text",
    )
    send_command.add_argument("--json", action="store_true", help="alias for --format json")
    send_command.add_argument("--dry-run", action="store_true", help="preview the request without sending it")
    stop = sub.add_parser("stop", formatter_class=KeysightHelpFormatter)
    stop.add_argument("--port", type=int, default=8765, help="server port; range 1-65535")
    stop.add_argument(
        "--timeout-ms",
        type=int,
        default=3000,
        help="HTTP client timeout in ms; supported range 100-600000",
    )
    stop.add_argument(
        "--format",
        dest="output_format",
        choices=["text", "json"],
        default="text",
        help="output format for the response; default: text",
    )
    stop.add_argument("--json", action="store_true", help="alias for --format json")
    stop.add_argument("--dry-run", action="store_true", help="preview the request without sending it")

    status = sub.add_parser("status", formatter_class=KeysightHelpFormatter)
    status.add_argument("--port", type=int, default=8765, help="server port; range 1-65535")
    status.add_argument(
        "--timeout-ms",
        type=int,
        default=3000,
        help="HTTP client timeout in ms; supported range 100-600000",
    )
    status.add_argument(
        "--format",
        dest="output_format",
        choices=["text", "json"],
        default="text",
        help="output format for the response; default: text",
    )
    status.add_argument("--json", action="store_true", help="alias for --format json")
    status.add_argument("--dry-run", action="store_true", help="preview the request without sending it")

    wait = sub.add_parser("wait-ready", formatter_class=KeysightHelpFormatter)
    wait.add_argument("--port", type=int, default=8765, help="server port; range 1-65535")
    wait.add_argument(
        "--timeout-ms",
        type=int,
        default=10000,
        help="overall wait deadline in ms; supported range 100-600000",
    )
    wait.add_argument(
        "--format",
        dest="output_format",
        choices=["text", "json"],
        default="text",
        help="output format for the response; default: text",
    )
    wait.add_argument("--json", action="store_true", help="alias for --format json")

    return parser
