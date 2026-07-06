from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .measurement import (
    MeasurementDefinition,
    format_measurement_type,
    get_measurement_definition,
    normalize_measurement_type,
    registered_measurement_types,
)
from .constants import UTC_PLUS_8
from .models import (
    InstrumentProfile,
    MeasurementOptions,
    StartRequest,
    get_default_instrument_profile,
)


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
AUTO_ZERO_MEASUREMENTS = ("current_dc", "voltage_dc", "resistance_2w")
DCV_INPUT_IMPEDANCE_MEASUREMENTS = ("voltage_dc", "voltage_dc_ratio")
DCV_INPUT_IMPEDANCE_OPTIONS = ("default", "10m", "auto")
CURRENT_MEASUREMENTS = ("current_dc", "current_ac")
FREQUENCY_PERIOD_MEASUREMENTS = ("frequency", "period")


@dataclass(frozen=True)
class CoreWarning:
    code: str
    message: str
    severity: str
    fields: dict[str, object]


@dataclass(frozen=True)
class _StartValidationContext:
    request: StartRequest
    trigger_mode: str
    custom_mode: bool
    profile: InstrumentProfile
    measurement_type: str
    definition: MeasurementDefinition
    options: MeasurementOptions


def resolve_csv_path(csv_path: str | None, now: datetime | None = None) -> Path:
    if csv_path is not None:
        return Path(csv_path)
    effective_now = now or datetime.now(UTC_PLUS_8)
    if effective_now.tzinfo is None:
        effective_now = effective_now.replace(tzinfo=UTC_PLUS_8)
    timestamp = effective_now.astimezone(UTC_PLUS_8).strftime("%Y-%m-%d-%H-%M-%S")
    return Path("data") / f"{timestamp}.csv"


def resolve_measurement_range(request: StartRequest) -> float | None:
    if request.measurement_range is not None and request.current_range is not None:
        raise ValueError("--range and --current-range cannot be used together")
    if request.measurement_range is not None:
        return request.measurement_range
    return request.current_range


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
    if definition.range_label == "amps":
        return "A"
    if definition.range_label == "volts":
        return "V"
    if definition.range_label == "ohms":
        return "Ohm"
    return definition.unit


def value_in_options(value: float, options: tuple[float, ...]) -> bool:
    return any(abs(float(value) - float(option)) <= 1e-12 for option in options)


def normalize_auto_zero(value: bool | str) -> str:
    if value is True:
        return "on"
    if value is False:
        return "off"
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ("on", "off", "once"):
            return normalized
    raise ValueError("--auto-zero must be one of: on, off, once")


def supported_measurement_types(profile: InstrumentProfile) -> tuple[str, ...]:
    registered_measurements = set(registered_measurement_types())
    return tuple(value for value in profile.supported_measurement_types if value in registered_measurements)


def supported_trigger_modes(profile: InstrumentProfile) -> tuple[str, ...]:
    modes = ["software", "immediate"]
    if profile.supports_external_trigger:
        modes.append("external")
    if profile.supports_buffered_reading_memory:
        modes.append("immediate-custom")
        if profile.supports_bus_trigger:
            modes.append("software-custom")
        if profile.supports_external_trigger:
            modes.append("external-custom")
    return tuple(modes)


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
    current_terminal_values: list[str] = []
    for measurement_name in measurement_names:
        definition = get_measurement_definition(measurement_name)
        options = effective_profile.get_measurement_options(measurement_name)
        for terminal in options.current_terminal_options:
            terminal_text = str(terminal)
            if terminal_text not in current_terminal_values:
                current_terminal_values.append(terminal_text)
        range_lines.append(
            f"  {definition.canonical_name}: {format_range_options(options)} {range_unit(definition)}"
        )
    current_terminal_line = (
        "  current terminal choices for supported current measurements: "
        + ", ".join(current_terminal_values)
        if current_terminal_values
        else "  current terminal selection is not supported by this profile"
    )
    return (
        "Limits:\n"
        "  instrument profile: live starts auto-detect when --model is omitted; "
        "use --model 34460A or --model 34461A to force model-specific limits\n"
        f"  measurement choices: {', '.join(measurement_names)}\n"
        "  NPLC choices for DC/resistance: 0.02, 0.2, 1, 10, 100\n"
        "  AC current/voltage and Frequency/Period do not support NPLC SCPI; "
        "omit --nplc or use 1.0\n"
        "  AC bandwidth choices for AC current/voltage and Frequency/Period: 3, 20, 200 Hz\n"
        "  Frequency/Period gate time choices: 0.01, 0.1, 1 s; default: 0.1 s\n"
        "  Frequency timeout choices: auto, 1s; default: auto; Period unsupported\n"
        f"{current_terminal_line}\n"
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
        f"  custom trigger_count * sample_count > {effective_profile.reading_memory_limit} "
        "requires --allow-buffer-overflow-risk for this profile"
    )


def validate_client_port(port: int) -> None:
    if port < CLIENT_PORT_RANGE[0] or port > CLIENT_PORT_RANGE[1]:
        raise ValueError(
            f"--port {port} is outside the supported range 1-65535. "
            "Use a TCP port from 1 to 65535."
        )


def resolve_trigger_mode(request: StartRequest) -> str:
    return request.trigger_mode or "software"


def validate_start_request(
    request: StartRequest,
    trigger_mode: str,
    instrument_profile: InstrumentProfile | None = None,
) -> None:
    _validate_basic_mode_conflicts(request)
    context = _resolve_start_validation_context(request, trigger_mode, instrument_profile)
    _validate_trigger_mode(context)
    _validate_measurement_preconditions(context)
    _validate_common_runtime_limits(context.request)
    measurement_range = _validate_measurement_option_values(context)
    _validate_hw_trigger_delay(context.request)
    _validate_manual_range_requirement(context, measurement_range)
    _validate_count_limits(context.request)
    _validate_timer_interval(context)
    _validate_buffer_drain_size(context)
    _validate_custom_mode_contract(context)


def _validate_basic_mode_conflicts(request: StartRequest) -> None:
    if request.dry_run and request.simulate:
        raise ValueError("--dry-run and --simulate cannot be used together")


def _resolve_start_validation_context(
    request: StartRequest,
    trigger_mode: str,
    instrument_profile: InstrumentProfile | None,
) -> _StartValidationContext:
    profile = instrument_profile or get_default_instrument_profile()
    measurement_type = normalize_measurement_type(request.measurement)
    supported_measurements = supported_measurement_types(profile)
    if measurement_type not in supported_measurements:
        choices = ", ".join(format_measurement_type(value) for value in supported_measurements)
        raise ValueError(f"--measurement must be one of: {choices}")
    definition = get_measurement_definition(measurement_type)
    return _StartValidationContext(
        request=request,
        trigger_mode=trigger_mode,
        custom_mode=trigger_mode.endswith("-custom"),
        profile=profile,
        measurement_type=measurement_type,
        definition=definition,
        options=profile.get_measurement_options(measurement_type),
    )


def _validate_measurement_preconditions(context: _StartValidationContext) -> None:
    args = context.request
    if not context.definition.accepts_current_range_alias and args.current_range is not None:
        raise ValueError("--current-range can only be used with --measurement current-dc")
    dcv_input_impedance = str(args.dcv_input_impedance).strip().lower()
    if dcv_input_impedance not in DCV_INPUT_IMPEDANCE_OPTIONS:
        raise ValueError("--dcv-input-impedance must be one of: default, 10m, auto")
    if (
        dcv_input_impedance != "default"
        and context.measurement_type not in DCV_INPUT_IMPEDANCE_MEASUREMENTS
    ):
        raise ValueError(
            "--dcv-input-impedance can only be used with --measurement "
            "voltage-dc or voltage-dc-ratio"
        )
    auto_zero = normalize_auto_zero(args.auto_zero)
    if context.measurement_type == "voltage_dc_ratio" and auto_zero != "on":
        raise ValueError(
            "--auto-zero for --measurement voltage-dc-ratio must be on/default; "
            "off and once are not supported"
        )
    if auto_zero == "once" and context.measurement_type not in AUTO_ZERO_MEASUREMENTS:
        raise ValueError(
            "--auto-zero once can only be used with --measurement current-dc, voltage-dc, "
            "or resistance-2w"
        )
    if args.measurement_range is not None and args.current_range is not None:
        raise ValueError("--range and --current-range cannot be used together")


def _validate_trigger_mode(context: _StartValidationContext) -> None:
    supported_modes = supported_trigger_modes(context.profile)
    if context.trigger_mode not in supported_modes:
        raise ValueError(
            f"--trigger-mode {context.trigger_mode} is not supported by "
            f"{context.profile.model}. Supported modes: {', '.join(supported_modes)}"
        )


def _validate_common_runtime_limits(args: StartRequest) -> None:
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


def _validate_measurement_option_values(context: _StartValidationContext) -> float | None:
    args = context.request
    definition = context.definition
    options = context.options
    if args.measurement_range is not None:
        allowed_ranges = tuple(value for _label, value in options.range_options)
        if not value_in_options(args.measurement_range, allowed_ranges):
            raise ValueError(
                f"--range {format_number(args.measurement_range)} is not valid for "
                f"--measurement {definition.canonical_name}. Allowed ranges in "
                f"{range_unit(definition)}: {format_range_options(options)}. "
                "Use one of the listed range values or omit --range with --auto-range on."
            )
    if args.current_range is not None:
        allowed_ranges = tuple(value for _label, value in options.range_options)
        if not value_in_options(args.current_range, allowed_ranges):
            raise ValueError(
                f"--current-range {format_number(args.current_range)} is not valid for "
                f"--measurement {definition.canonical_name}. Allowed ranges in "
                f"{range_unit(definition)}: {format_range_options(options)}. "
                "Use one of the listed current range values."
            )
    measurement_range = resolve_measurement_range(args)
    if args.ac_bandwidth_hz is not None:
        if not options.ac_bandwidth_hz_options:
            raise ValueError(
                "--ac-bandwidth-hz can only be used with --measurement current-ac, voltage-ac, "
                "frequency, or period"
            )
        if not value_in_options(args.ac_bandwidth_hz, options.ac_bandwidth_hz_options):
            raise ValueError(
                f"--ac-bandwidth-hz {format_number(args.ac_bandwidth_hz)} is not valid for "
                f"--measurement {definition.canonical_name}. Allowed AC bandwidth values in Hz: "
                f"{format_values(options.ac_bandwidth_hz_options)}."
            )
    if args.gate_time_s is not None:
        if not options.gate_time_s_options:
            raise ValueError(
                "--gate-time-s can only be used with --measurement frequency or period"
            )
        if not value_in_options(args.gate_time_s, options.gate_time_s_options):
            raise ValueError(
                f"--gate-time-s {format_number(args.gate_time_s)} is not valid for "
                f"--measurement {definition.canonical_name}. Allowed gate time values in s: "
                f"{format_values(options.gate_time_s_options)}."
            )
    if args.freq_period_timeout is not None:
        normalized_freq_period_timeout = str(args.freq_period_timeout).strip().lower()
        if not options.freq_period_timeout_options:
            raise ValueError(
                f"--freq-period-timeout is not supported for --measurement "
                f"{definition.canonical_name}"
            )
        if normalized_freq_period_timeout not in options.freq_period_timeout_options:
            raise ValueError(
                f"--freq-period-timeout {args.freq_period_timeout} is not valid for "
                f"--measurement {definition.canonical_name}. Allowed values: "
                f"{', '.join(options.freq_period_timeout_options)}."
            )
    if args.current_terminal is not None:
        if not options.current_terminal_options:
            raise ValueError(
                "--current-terminal can only be used with --measurement current-dc or current-ac"
            )
        if args.current_terminal not in options.current_terminal_options:
            raise ValueError(
                f"--current-terminal {args.current_terminal} is not valid for "
                f"--measurement {definition.canonical_name}. Allowed current terminals: "
                f"{', '.join(str(value) for value in options.current_terminal_options)}."
            )
    _validate_current_terminal_range_pairing(context, measurement_range)
    if options.nplc_options:
        if not value_in_options(args.nplc, options.nplc_options):
            raise ValueError(
                f"--nplc {format_number(args.nplc)} is not valid for "
                f"--measurement {definition.canonical_name}. Allowed NPLC values: "
                f"{format_values(options.nplc_options)}. Use one of the listed values."
            )
    elif args.nplc != NEUTRAL_AC_NPLC:
        if context.measurement_type in FREQUENCY_PERIOD_MEASUREMENTS:
            raise ValueError(
                f"--nplc {format_number(args.nplc)} is not valid for "
                f"--measurement {definition.canonical_name}. Frequency and Period do not "
                "support NPLC SCPI. Omit --nplc or use the neutral default value 1.0."
            )
        raise ValueError(
            f"--nplc {format_number(args.nplc)} is not valid for "
            f"--measurement {definition.canonical_name}. AC measurements do not support NPLC SCPI. "
            "Omit --nplc or use the neutral default value 1.0."
        )
    return measurement_range


def _validate_current_terminal_range_pairing(
    context: _StartValidationContext,
    measurement_range: float | None,
) -> None:
    args = context.request
    if context.measurement_type not in CURRENT_MEASUREMENTS or measurement_range is None:
        return
    is_10a_range = value_in_options(measurement_range, (10.0,))
    if args.current_terminal == 3 and is_10a_range:
        raise ValueError("--current-terminal 3 cannot be used with the 10 A current range")
    if is_10a_range and args.current_terminal != 10:
        raise ValueError("10 A current range requires --current-terminal 10")
    if args.current_terminal == 10 and not is_10a_range:
        raise ValueError("--current-terminal 10 requires the 10 A current range")


def _validate_hw_trigger_delay(args: StartRequest) -> None:
    validate_float_range(
        "--hw-trigger-delay-s",
        args.hw_trigger_delay_s,
        *HW_TRIGGER_DELAY_S_RANGE,
        "s",
    )


def _validate_manual_range_requirement(
    context: _StartValidationContext,
    measurement_range: float | None,
) -> None:
    args = context.request
    if not args.auto_range and measurement_range is None and context.measurement_type == "current_dc":
        raise ValueError("--range or --current-range is required when --auto-range off")
    if not args.auto_range and measurement_range is None:
        raise ValueError("--range is required when --auto-range off")


def _validate_count_limits(args: StartRequest) -> None:
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


def _validate_timer_interval(context: _StartValidationContext) -> None:
    args = context.request
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
        if context.trigger_mode != "software":
            raise ValueError("--timer-interval-s requires --trigger-mode software")


def _validate_buffer_drain_size(context: _StartValidationContext) -> None:
    args = context.request
    if args.buffer_drain_size is not None:
        max_buffer_drain_size = min(
            BUFFER_DRAIN_SIZE_RANGE[1],
            context.profile.reading_memory_limit,
        )
        validate_int_range(
            "--buffer-drain-size",
            args.buffer_drain_size,
            BUFFER_DRAIN_SIZE_RANGE[0],
            max_buffer_drain_size,
            f"{context.profile.model} reading-memory",
        )
        if not context.custom_mode:
            raise ValueError("--buffer-drain-size requires a custom trigger mode")


def _validate_custom_mode_contract(context: _StartValidationContext) -> None:
    args = context.request
    if args.allow_buffer_overflow_risk and not context.custom_mode:
        raise ValueError("--allow-buffer-overflow-risk requires a custom trigger mode")
    if context.custom_mode:
        if args.max_samples is not None:
            raise ValueError("--max-samples cannot be used with custom trigger modes")
        if args.trigger_count is None:
            raise ValueError("--trigger-count is required with custom trigger modes")
        if args.sample_count is None:
            raise ValueError("--sample-count is required with custom trigger modes")
        memory_limit = context.profile.reading_memory_limit
        expected_readings = args.trigger_count * args.sample_count
        if expected_readings > memory_limit and not args.allow_buffer_overflow_risk:
            raise ValueError(
                f"custom mode expected readings {expected_readings} exceed "
                f"{context.profile.model} reading memory {memory_limit}; "
                "add --allow-buffer-overflow-risk to proceed."
            )
    else:
        if args.trigger_count is not None:
            raise ValueError("--trigger-count requires a custom trigger mode")
        if args.sample_count is not None:
            raise ValueError("--sample-count requires a custom trigger mode")
        if getattr(args, "simulate", False) and args.max_samples is None:
            raise ValueError("--simulate requires --max-samples with simple trigger modes")


def generate_buffer_overflow_warnings(
    request: StartRequest,
    trigger_mode: str,
    instrument_profile: InstrumentProfile | None = None,
) -> list[str]:
    return [
        warning.message
        for warning in generate_buffer_overflow_warning_details(
            request,
            trigger_mode,
            instrument_profile,
        )
    ]


def generate_buffer_overflow_warning_details(
    request: StartRequest,
    trigger_mode: str,
    instrument_profile: InstrumentProfile | None = None,
) -> list[CoreWarning]:
    args = request
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
    fields = {
        "trigger_mode": trigger_mode,
        "trigger_count": args.trigger_count,
        "sample_count": args.sample_count,
        "expected_readings": expected_readings,
        "memory_limit": memory_limit,
        "model": model,
    }
    return [
        CoreWarning("buffer_overflow_risk", msg1, "warning", dict(fields)),
        CoreWarning("buffer_overflow_counts", msg2, "warning", dict(fields)),
        CoreWarning("buffer_overflow_drain_rate", msg3, "warning", dict(fields)),
        CoreWarning("buffer_overflow_data_loss", msg4, "warning", dict(fields)),
        CoreWarning("buffer_overflow_validation", msg5, "warning", dict(fields)),
    ]


validate_start_args = validate_start_request
