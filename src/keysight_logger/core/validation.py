from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from .measurement import (
    format_measurement_type,
    get_measurement_definition,
    normalize_measurement_type,
    registered_measurement_types,
)
from .models import InstrumentProfile, get_default_instrument_profile
from .storage import UTC_PLUS_8


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


def format_number(value: float | int) -> str:
    numeric = float(value)
    if numeric.is_integer():
        return str(int(numeric))
    return f"{numeric:g}"


def format_values(values: tuple[float, ...]) -> str:
    return ", ".join(format_number(value) for value in values)


def format_range_options(options) -> str:  # noqa: ANN001
    return format_values(tuple(value for _label, value in options.range_options))


def range_unit(definition) -> str:  # noqa: ANN001
    if definition.unit == "A":
        return "A"
    if definition.unit == "V":
        return "V"
    return "Ohm"


def value_in_options(value: float, options: tuple[float, ...]) -> bool:
    return any(abs(float(value) - float(option)) <= 1e-12 for option in options)


def supported_measurement_types(profile: InstrumentProfile) -> tuple[str, ...]:
    registered_measurements = set(registered_measurement_types())
    return tuple(value for value in profile.supported_measurement_types if value in registered_measurements)


def validate_int_range(name: str, value: int, minimum: int, maximum: int, detail: str) -> None:
    if value < minimum or value > maximum:
        raise ValueError(
            f"{name} {value} is outside the {detail} range {minimum}-{maximum}. "
            f"Use a value from {minimum} to {maximum}."
        )


def validate_float_range(
    name: str,
    value: float,
    minimum: float,
    maximum: float,
    unit: str,
) -> None:
    if value < minimum or value > maximum:
        raise ValueError(
            f"{name} {format_number(value)} is outside the supported range "
            f"{format_number(minimum)}-{format_number(maximum)} {unit}. "
            f"Use a value from {format_number(minimum)} to {format_number(maximum)} {unit}."
        )


def start_help_epilog(profile: InstrumentProfile | None = None) -> str:
    effective_profile = profile or get_default_instrument_profile()
    measurement_names = [
        format_measurement_type(value) for value in supported_measurement_types(effective_profile)
    ]
    range_lines = []
    for measurement_name in measurement_names:
        definition = get_measurement_definition(measurement_name)
        options = effective_profile.get_measurement_options(measurement_name)
        range_lines.append(
            f"  {definition.cli_name}: {format_range_options(options)} {definition.unit}"
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
    supported_measurements = supported_measurement_types(profile)
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
    validate_int_range("--timeout-ms", args.timeout_ms, *TIMEOUT_MS_RANGE, "supported")
    validate_int_range(
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
    validate_int_range("--sw-queue-max", args.sw_queue_max, *SW_QUEUE_MAX_RANGE, "supported")
    if args.measurement_range is not None:
        allowed_ranges = tuple(value for _label, value in options.range_options)
        if not value_in_options(args.measurement_range, allowed_ranges):
            raise ValueError(
                f"--range {format_number(args.measurement_range)} is not valid for "
                f"--measurement {definition.cli_name}. Allowed ranges in "
                f"{range_unit(definition)}: {format_range_options(options)}. "
                "Use one of the listed range values or omit --range with --auto-range on."
            )
    if args.current_range is not None:
        allowed_ranges = tuple(value for _label, value in options.range_options)
        if not value_in_options(args.current_range, allowed_ranges):
            raise ValueError(
                f"--current-range {format_number(args.current_range)} is not valid for "
                f"--measurement {definition.cli_name}. Allowed ranges in "
                f"{range_unit(definition)}: {format_range_options(options)}. "
                "Use one of the listed current range values."
            )
    measurement_range = resolve_measurement_range(args)
    if options.nplc_options:
        if not value_in_options(args.nplc, options.nplc_options):
            raise ValueError(
                f"--nplc {format_number(args.nplc)} is not valid for "
                f"--measurement {definition.cli_name}. Allowed NPLC values: "
                f"{format_values(options.nplc_options)}. Use one of the listed values."
            )
    elif args.nplc != NEUTRAL_AC_NPLC:
        raise ValueError(
            f"--nplc {format_number(args.nplc)} is not valid for "
            f"--measurement {definition.cli_name}. AC measurements do not support NPLC SCPI. "
            "Omit --nplc or use the neutral default value 1.0."
        )
    validate_float_range(
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
        validate_int_range("--max-samples", args.max_samples, *MAX_SAMPLES_RANGE, "supported")
    if args.trigger_count is not None:
        validate_int_range(
            "--trigger-count",
            args.trigger_count,
            *TRIGGER_COUNT_RANGE,
            "34461A supported",
        )
    if args.sample_count is not None:
        validate_int_range(
            "--sample-count",
            args.sample_count,
            *SAMPLE_COUNT_RANGE,
            "34461A supported",
        )
    if args.timer_interval_s is not None:
        if args.timer_interval_s < TIMER_INTERVAL_S_RANGE[0]:
            raise ValueError(
                f"--timer-interval-s {format_number(args.timer_interval_s)} is below "
                f"the supported minimum {format_number(TIMER_INTERVAL_S_RANGE[0])} s. "
                "This is a PC-side timer and is not reliable below 0.5 s."
            )
        if args.timer_interval_s > TIMER_INTERVAL_S_RANGE[1]:
            raise ValueError(
                f"--timer-interval-s {format_number(args.timer_interval_s)} is outside "
                "the supported range 0.5-86400 s. Use a value from 0.5 to 86400 s."
            )
        if trigger_mode != "software":
            raise ValueError("--timer-interval-s requires --trigger-mode software")
    if args.buffer_drain_size is not None:
        max_buffer_drain_size = min(BUFFER_DRAIN_SIZE_RANGE[1], profile.reading_memory_limit)
        validate_int_range(
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
