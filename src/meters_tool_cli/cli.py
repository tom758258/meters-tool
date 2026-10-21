from __future__ import annotations

import argparse
import json
import signal  # noqa: F401  # compatibility patch path
import sys
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

from meters_tool_core import (
    SUPPORT_POLICY_MODE_PRODUCT,
    SUPPORT_POLICY_MODE_VALIDATION,
    StartRequest,
    StartRunEvent,
    build_start_plan,
    generate_buffer_overflow_warnings,
    get_core_capabilities,
    resolve_instrument_profile,
    resolve_trigger_mode,
    run_start_session,
    start_workflow_support,
    validate_start_request,
    validate_start_workflow_support,
)
from meters_tool_core._version import (
    DISTRIBUTION_NAME,
    FALLBACK_PACKAGE_VERSION,
    get_distribution_version,
)
from meters_tool_core.instrument import InstrumentError, VisaInstrument
from meters_tool_core.session import new_run_id
from meters_tool_core.start_resolution import resolve_start_profile
from meters_tool_core.streaming import RunBoundStreamState
from meters_tool_core.validation import (
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

try:
    from ._constants import CLI_EVENT_SCHEMA_VERSION
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
        MetersArgumentParser,
        MetersHelpFormatter,
        build_parser as _build_parser,
        parse_auto_zero,
        parse_dcv_input_impedance,
        parse_on_off,
    )
    from ._runtime_output import CliEventEmitter, CliStartRunEventSink, _emit_start_plan
    from ._start_controls import (
        CliStartRunControls,
        WindowsConsoleStopHandler,
        WindowsKeyboardStopPoller,
    )
except ImportError:  # pragma: no cover - PyInstaller script entry point
    from meters_tool_cli._constants import CLI_EVENT_SCHEMA_VERSION
    from meters_tool_cli._client_commands import (
        _validate_client_port_and_timeout,
        cmd_send_command,
        cmd_status,
        cmd_stop,
        cmd_wait_ready,
    )
    from meters_tool_cli._parser import (
        build_parser as _build_parser,
    )
    from meters_tool_cli._runtime_output import (
        CliEventEmitter,
        CliStartRunEventSink,
        _emit_start_plan,
    )
    from meters_tool_cli._start_controls import (
        CliStartRunControls,
        WindowsConsoleStopHandler,  # noqa: F401  # compatibility import
        WindowsKeyboardStopPoller,  # noqa: F401  # compatibility import
    )

__all__ = [
    "CommandResponsePayloadError",
    "MetersArgumentParser",
    "MetersHelpFormatter",
    "StatusPayloadError",
    "parse_auto_zero",
    "parse_dcv_input_impedance",
    "parse_on_off",
    "validate_client_timeout_ms",
]

FALLBACK_CLI_VERSION = FALLBACK_PACKAGE_VERSION

_USER_GUIDE_FILENAMES = {
    "en": "cli.html",
    "zh-TW": "cli.zh-TW.html",
}


def _resolve_user_guide_path(lang: str) -> Path:
    return Path(__file__).resolve().parent / "help" / _USER_GUIDE_FILENAMES[lang]


def cmd_user_guide(lang: str = "en") -> int:
    guide_path = _resolve_user_guide_path(lang)
    if not guide_path.is_file():
        print(f"Bundled CLI user guide not found: {guide_path}", file=sys.stderr)
        return 1
    try:
        opened = webbrowser.open_new_tab(guide_path.as_uri())
    except (OSError, webbrowser.Error) as exc:
        print(f"Failed to open bundled CLI user guide: {guide_path} ({exc})", file=sys.stderr)
        return 1
    if not opened:
        print(f"Failed to open bundled CLI user guide: {guide_path}", file=sys.stderr)
        return 1
    return 0


def get_cli_version() -> str:
    return get_distribution_version(
        distribution_name=DISTRIBUTION_NAME,
        fallback=FALLBACK_CLI_VERSION,
    )


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None

def _normalize_serial_termination(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().upper()
    if normalized == "CRLF":
        return "\r\n"
    if normalized == "LF":
        return "\n"
    if normalized == "CR":
        return "\r"
    if normalized == "NONE":
        return None
    raise ValueError("serial termination must be CRLF, LF, CR, or NONE")

def _start_request_from_args(args: argparse.Namespace) -> StartRequest:
    return StartRequest(
        resource=args.resource,
        instrument_model=_optional_text(args.instrument_model),
        visa_library=_optional_text(args.visa_library),
        csv=_optional_text(args.csv),
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
        trigger_count_infinite=args.trigger_count_infinite,
        monitor_overflow=args.monitor_overflow,
        stop_on_overflow=args.stop_on_overflow,
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
        csv_enabled=(
            not args.no_csv
            and (not args.streaming or _optional_text(args.csv) is not None)
        ),
        csv_format=args.csv_format,
        csv_time_columns=tuple(filter(None, (value.strip() for value in args.csv_time_columns.split(",")))),
    )

def build_parser() -> argparse.ArgumentParser:
    return _build_parser(get_cli_version)


def _range_payload(values: tuple[int | float, int | float]) -> dict[str, int | float]:
    return {"min": values[0], "max": values[1]}


def _support_scope_payload(scope) -> dict[str, object]:  # noqa: ANN001
    return {
        "backend_scope": scope.backend_scope,
        "features": [
            {
                "feature_kind": feature.feature_kind,
                "feature_value": feature.feature_value,
                "validation_status": feature.validation_status,
            }
            for feature in scope.feature_scopes
        ],
        "transport_scope": scope.transport_scope,
        "validation_status": scope.validation_status,
    }


def _support_payload(profile) -> dict[str, object]:  # noqa: ANN001
    return {
        command: {
            mode: {
                "backend_scope": support.backend_scope,
                "scopes": [_support_scope_payload(scope) for scope in support.scopes],
                "transport_scope": support.transport_scope,
                "validation_status": support.validation_status,
            }
            for mode, support in modes.items()
        }
        for command, modes in start_workflow_support(profile).items()
    }


def cmd_capabilities(
    model: str | None = None,
    output_format: str = "text",
    print_fn=print,  # noqa: ANN001
) -> int:
    requested_model = _optional_text(model)
    try:
        profile = resolve_instrument_profile(requested_model)
    except ValueError as exc:
        if output_format == "json":
            print_fn(
                json.dumps(
                    {
                        "command": "capabilities",
                        "event": "error",
                        "exit_code": 2,
                        "message": str(exc),
                        "requested_model": requested_model,
                        "schema_version": CLI_EVENT_SCHEMA_VERSION,
                        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    },
                    sort_keys=True,
                )
            )
        else:
            print(str(exc), file=sys.stderr)
        return 2

    capabilities = get_core_capabilities(profile)
    payload = {
        "available_profiles": list(capabilities.available_profiles),
        "capability_profile": {
            "model": capabilities.model,
            "model_id": capabilities.model_id,
            "reading_memory_limit": capabilities.reading_memory_limit,
            "supports_buffered_reading_memory": profile.supports_buffered_reading_memory,
            "vendor": capabilities.vendor,
        },
        "event": "capabilities",
        "limits": {
            "buffer_drain_size": _range_payload(
                (
                    BUFFER_DRAIN_SIZE_RANGE[0],
                    min(BUFFER_DRAIN_SIZE_RANGE[1], capabilities.reading_memory_limit),
                )
            ),
            "hw_trigger_delay_s": _range_payload(HW_TRIGGER_DELAY_S_RANGE),
            "max_samples": _range_payload(MAX_SAMPLES_RANGE),
            "sample_count": _range_payload(SAMPLE_COUNT_RANGE),
            "sw_min_interval_ms": {
                **_range_payload(SW_MIN_INTERVAL_MS_RANGE),
                "nonzero_min": 50,
            },
            "sw_queue_max": _range_payload(SW_QUEUE_MAX_RANGE),
            "timeout_ms": _range_payload(TIMEOUT_MS_RANGE),
            "timer_interval_s": _range_payload(TIMER_INTERVAL_S_RANGE),
            "trigger_count": _range_payload(TRIGGER_COUNT_RANGE),
            "trigger_timeout_ms": _range_payload(TRIGGER_TIMEOUT_MS_RANGE),
        },
        "measurements": [
            {
                "ac_bandwidth_hz_values": list(measurement.ac_bandwidth_hz_values),
                "auto_zero_values": list(measurement.auto_zero_values),
                "current_terminal_values": list(measurement.current_terminal_values),
                "dcv_input_impedance_values": list(measurement.dcv_input_impedance_values),
                "default_ac_bandwidth_hz": measurement.default_ac_bandwidth_hz,
                "default_auto_range": measurement.default_auto_range,
                "default_freq_period_timeout": measurement.default_freq_period_timeout,
                "default_gate_time_s": measurement.default_gate_time_s,
                "freq_period_timeout_values": list(measurement.freq_period_timeout_values),
                "gate_time_s_values": list(measurement.gate_time_s_values),
                "measurement_name": measurement.measurement_name,
                "measurement_type": measurement.measurement_type,
                "nplc_values": list(measurement.nplc_values),
                "range_values": list(measurement.range_values),
                "unit": measurement.unit,
            }
            for measurement in capabilities.measurements
        ],
        "runtime_identity": {
            "detection_performed": False,
            "model": None,
            "model_id": None,
            "vendor": None,
        },
        "schema_version": CLI_EVENT_SCHEMA_VERSION,
        "selection": {
            "requested_model": requested_model,
            "source": "requested_model" if requested_model is not None else "default_fallback",
        },
        "support": _support_payload(profile),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "trigger_modes": list(capabilities.trigger_modes),
    }

    if output_format == "json":
        print_fn(json.dumps(payload, sort_keys=True))
        return 0

    source_label = "requested model" if requested_model is not None else "default fallback"
    print_fn(
        "capability profile: "
        f"{capabilities.vendor} {capabilities.model} ({capabilities.model_id})"
    )
    print_fn(f"profile source: {source_label}")
    print_fn("runtime identity detection: not performed")
    print_fn(
        "available profiles: "
        + ", ".join(item["model"] for item in capabilities.available_profiles)
    )
    print_fn(
        "measurements: "
        + ", ".join(measurement.measurement_name for measurement in capabilities.measurements)
    )
    print_fn("trigger modes: " + ", ".join(capabilities.trigger_modes))
    return 0


def cmd_manifest(output_format: str = "text", print_fn=print) -> int:  # noqa: ANN001
    if output_format not in {"text", "json"}:
        raise ValueError("output_format must be 'text' or 'json'")

    payload = {
        "event": "tool_manifest",
        "schema_version": CLI_EVENT_SCHEMA_VERSION,
        "tool_id": "meters",
        "tool_version": get_cli_version(),
        "worker_protocol": {
            "compatibility_policy": "v2-only",
            "schema_versions": [CLI_EVENT_SCHEMA_VERSION],
        },
    }

    if output_format == "json":
        print_fn(json.dumps(payload, sort_keys=True))
        return 0

    print_fn(f"tool id: {payload['tool_id']}")
    print_fn(f"tool version: {payload['tool_version']}")
    print_fn(
        "worker protocol: "
        f"schema versions {payload['worker_protocol']['schema_versions']} "
        f"({payload['worker_protocol']['compatibility_policy']})"
    )
    return 0


def cmd_list_resources(
    verify: bool = False,
    live_only: bool = False,
    output_format: str = "text",
    dry_run: bool = False,
    visa_library: str | None = None,
    serial_read_termination: str | None = None,
    serial_write_termination: str | None = None,
    print_fn=print,  # noqa: ANN001
    resource_manager_factory=None,  # noqa: ANN001
) -> int:
    if output_format not in {"text", "json"}:
        raise ValueError("output_format must be 'text' or 'json'")

    effective_verify = verify or live_only
    normalized_visa_library = _optional_text(visa_library)
    normalized_serial_read_termination = _normalize_serial_termination(serial_read_termination)
    normalized_serial_write_termination = _normalize_serial_termination(serial_write_termination)
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
                "release_to_local_after_successful_non_asrl_verify": False,
                "release_to_local_after_successful_verify": False,
                "serial_termination_applies_to_asrl_only": True,
            },
            "schema_version": CLI_EVENT_SCHEMA_VERSION,
            "serial_read_termination": serial_read_termination,
            "serial_write_termination": serial_write_termination,
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
            print_fn(f"  serial_read_termination: {serial_read_termination or 'default'}")
            print_fn(f"  serial_write_termination: {serial_write_termination or 'default'}")
            print_fn(f"  effective_verify: {str(effective_verify).lower()}")
            print_fn("  dry_run_performs_visa_io: false")
            print_fn("  VISA I/O: no")
            print_fn("  planned real-run actions:")
            print_fn(f"    list VISA resources: {'yes' if actions['list_visa_resources'] else 'no'}")
            print_fn(f"    open each resource: {'yes' if actions['open_each_resource'] else 'no'}")
            print_fn(f"    query *IDN?: {'yes' if actions['query_idn'] else 'no'}")
            print_fn(
                "    release_to_local after successful non-ASRL verify: "
                f"{'yes' if actions['release_to_local_after_successful_non_asrl_verify'] else 'no'}"
            )
            print_fn("    serial termination applies to ASRL only: yes")
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
        try:
            ok, detail = VisaInstrument.verify_resource(
                resource,
                resource_manager_factory=resource_manager_factory,
                visa_library=normalized_visa_library,
                serial_read_termination=normalized_serial_read_termination,
                serial_write_termination=normalized_serial_write_termination,
            )
        except Exception as exc:
            ok = False
            detail = f"{type(exc).__name__}: {exc}"
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
    support_policy_mode = (
        SUPPORT_POLICY_MODE_VALIDATION
        if getattr(args, "validation_allow_pending_live_support", False)
        else SUPPORT_POLICY_MODE_PRODUCT
    )
    request_model: StartRequest
    try:
        if args.streaming and args.status_format != "jsonl":
            raise ValueError("--streaming requires --status-format jsonl or --json")
        request_model = _start_request_from_args(args)
        request_model, instrument_profile = resolve_start_profile(request_model)
        trigger_mode = resolve_trigger_mode(request_model)
        validate_start_request(request_model, trigger_mode, instrument_profile=instrument_profile)
        validate_start_workflow_support(
            request_model,
            trigger_mode,
            instrument_profile,
            support_policy_mode=support_policy_mode,
        )
    except ValueError as exc:
        emitter.error(str(exc), rc=2)
        return 2
    except InstrumentError as exc:
        emitter.error(str(exc), rc=3)
        return 3
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
    stream_state = RunBoundStreamState(runtime_run_id) if args.streaming else None
    for warning in warnings:
        if args.status_format == "jsonl":
            event_sink.emit(StartRunEvent.status_event(
                runtime_run_id, warning,
                **(stream_state.status_fields() if stream_state is not None else {}),
            ))
        else:
            emitter.line(warning)

    try:
        result = run_start_session(
            request_model,
            trigger_mode,
            instrument_profile,
            event_sink,
            CliStartRunControls(),
            run_id=runtime_run_id,
            support_policy_mode=support_policy_mode,
            **({"stream_state": stream_state} if stream_state is not None else {}),
        )
    except ValueError as exc:
        emitter.error(str(exc), rc=2)
        return 2
    except InstrumentError as exc:
        emitter.error(str(exc), rc=3)
        return 3
    return 0 if result.ok else 3

def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "capabilities":
        return cmd_capabilities(args.instrument_model, args.output_format)
    if args.command == "manifest":
        return cmd_manifest(args.output_format)
    if args.command == "list-resources":
        return cmd_list_resources(
            verify=args.verify,
            live_only=args.live_only,
            output_format=args.output_format,
            dry_run=args.dry_run,
            visa_library=args.visa_library,
            serial_read_termination=args.serial_read_termination,
            serial_write_termination=args.serial_write_termination,
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
    if args.command == "user-guide":
        return cmd_user_guide(args.lang)
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
