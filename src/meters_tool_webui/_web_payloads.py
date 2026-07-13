from __future__ import annotations

from typing import Any

from meters_tool_core import (
    FEATURE_KIND_MEASUREMENT,
    FEATURE_KIND_TRIGGER_MODE,
    start_workflow_support,
)
from meters_tool_core.constants import UTC_PLUS_8
from meters_tool_core.measurement import (
    format_measurement_type,
    get_measurement_definition,
    registered_measurement_types,
)
from meters_tool_core.models import INSTRUMENT_PROFILES, find_instrument_profile_by_idn
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
    supported_trigger_modes,
)


def build_capabilities_payload(
    profile: Any,
    *,
    auto_unresolved: bool,
    package_name: str,
    package_version: str,
) -> dict[str, Any]:
    measurements = []
    registered = set(registered_measurement_types())
    for measurement_type in profile.supported_measurement_types:
        if measurement_type not in registered:
            continue
        definition = get_measurement_definition(measurement_type)
        options = profile.get_measurement_options(measurement_type)
        ac_bandwidth_hz_options = list(getattr(options, "ac_bandwidth_hz_options", ()))
        gate_time_s_options = list(getattr(options, "gate_time_s_options", ()))
        freq_period_timeout_options = list(
            getattr(options, "freq_period_timeout_options", ())
        )
        current_terminal_options = list(getattr(options, "current_terminal_options", ()))
        measurements.append(
            {
                "name": definition.canonical_name,
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
                "ac_bandwidth_hz_options": ac_bandwidth_hz_options,
                "gate_time_s_options": gate_time_s_options,
                "freq_period_timeout_options": freq_period_timeout_options,
                "current_terminal_options": current_terminal_options,
                "supports_ac_bandwidth": bool(ac_bandwidth_hz_options),
                "supports_gate_time": bool(gate_time_s_options),
                "supports_freq_period_timeout": bool(freq_period_timeout_options),
                "supports_current_terminal": bool(current_terminal_options),
                "defaults": {
                    "auto_range": options.default_auto_range,
                    "ac_bandwidth_hz": options.default_ac_bandwidth_hz,
                    "gate_time_s": options.default_gate_time_s,
                    "freq_period_timeout": options.default_freq_period_timeout,
                },
            }
        )

    return {
        "app": {"name": package_name, "version": package_version},
        "instrument_profile": {
            "vendor": profile.vendor,
            "model": profile.model,
            "model_id": profile.model_id,
            "reading_memory_limit": profile.reading_memory_limit,
            "supports_buffered_reading_memory": profile.supports_buffered_reading_memory,
            "supports_bus_trigger": profile.supports_bus_trigger,
            "supports_external_trigger": profile.supports_external_trigger,
            "supports_sample_timer": profile.supports_sample_timer,
        },
        "support": {
            command: {
                mode: {
                    "validation_status": support.validation_status,
                    "transport_scope": support.transport_scope,
                    "backend_scope": support.backend_scope,
                    "scopes": [support_scope_payload(scope) for scope in support.scopes],
                }
                for mode, support in modes.items()
            }
            for command, modes in start_workflow_support(profile).items()
        },
        "support_summary": support_summary(profile, auto_unresolved=auto_unresolved),
        "available_profiles": [
            {
                "model": available.model,
                "model_id": available.model_id,
                "vendor": available.vendor,
            }
            for available in INSTRUMENT_PROFILES
        ],
        "measurements": measurements,
        "trigger_modes": list(supported_trigger_modes(profile)),
        "limits": {
            "timeout_ms": range_limit(TIMEOUT_MS_RANGE),
            "trigger_timeout_ms": range_limit(TRIGGER_TIMEOUT_MS_RANGE),
            "max_samples": range_limit(MAX_SAMPLES_RANGE),
            "trigger_count": range_limit(TRIGGER_COUNT_RANGE),
            "sample_count": range_limit(SAMPLE_COUNT_RANGE),
            "timer_interval_s": range_limit(TIMER_INTERVAL_S_RANGE),
            "buffer_drain_size": range_limit(
                (
                    BUFFER_DRAIN_SIZE_RANGE[0],
                    min(BUFFER_DRAIN_SIZE_RANGE[1], profile.reading_memory_limit),
                )
            ),
            "hw_trigger_delay_s": range_limit(HW_TRIGGER_DELAY_S_RANGE),
            "sw_min_interval_ms": {
                **range_limit(SW_MIN_INTERVAL_MS_RANGE),
                "nonzero_min": 50,
            },
            "sw_queue_max": range_limit(SW_QUEUE_MAX_RANGE),
        },
        "defaults": {
            "measurement": "current-dc",
            "instrument_model": None if auto_unresolved else profile.model,
            "trigger_mode": "software",
            "timeout_ms": 5000,
            "trigger_timeout_ms": 10000,
            "nplc": 1.0,
            "auto_zero": "on",
            "auto_range": True,
            "dcv_input_impedance": "default",
            "hw_trigger_slope": "neg",
            "hw_trigger_delay_s": 0.0,
            "ac_bandwidth_hz": None,
            "gate_time_s": None,
            "freq_period_timeout": None,
            "current_terminal": None,
        },
        "model_resolution": {
            "mode": "auto" if auto_unresolved else "explicit",
            "resolved": not auto_unresolved,
            "fallback_profile": profile.model if auto_unresolved else None,
            "fallback_profile_id": profile.model_id if auto_unresolved else None,
        },
    }


def resource_model_metadata(idn_detail: str | None) -> dict[str, Any]:
    if not idn_detail:
        return {
            "instrument_model": None,
            "instrument_model_id": None,
            "matched_profile": None,
        }
    try:
        profile = find_instrument_profile_by_idn(idn_detail)
    except ValueError:
        return {
            "instrument_model": None,
            "instrument_model_id": None,
            "matched_profile": None,
        }
    return {
        "instrument_model": profile.model,
        "instrument_model_id": profile.model_id,
        "matched_profile": {
            "vendor": profile.vendor,
            "model": profile.model,
            "model_id": profile.model_id,
        },
    }


def support_summary(profile: Any, *, auto_unresolved: bool = False) -> dict[str, Any]:
    live_support = start_workflow_support(profile)["start-trigger-record"]["live"]
    common = {
        "display_model": "Auto-detect" if auto_unresolved else profile.model,
        "capability_profile": profile.model,
        "capability_profile_id": profile.model_id,
        "model_id": profile.model_id,
        "is_fallback_capability_view": auto_unresolved,
        "runtime_driver_note": "Live runtime model is selected from detected *IDN?.",
        "runtime_driver_note_key": "support.runtime_driver.detected_idn",
        "scopes": [support_scope_payload(scope) for scope in live_support.scopes],
    }
    if profile.model == "34460A":
        return {
            **common,
            "model": "34460A",
            "validation_status": live_support.validation_status,
            "transport_scope": live_support.transport_scope,
            "backend_scope": live_support.backend_scope,
            "status_text": "USB/system-VISA full-suite validated.",
            "status_key": "support.status.usb_system_visa_validated",
            "open_workflows": [
                "immediate",
                "software",
                "software timer",
                "custom buffered",
                "Frequency",
                "Period",
            ],
            "open_workflow_keys": [
                "support.workflow.immediate",
                "support.workflow.software",
                "support.workflow.software_timer",
                "support.workflow.custom_buffered",
                "support.workflow.frequency",
                "support.workflow.period",
            ],
            "limits": [
                "no 10 A current path",
                "no current-terminal selection",
                "1000-reading memory limit",
                "no base-profile external trigger support",
            ],
            "limit_keys": [
                "support.limit.no_10a_current_path",
                "support.limit.no_current_terminal_selection",
                "support.limit.reading_memory_1000",
                "support.limit.no_base_profile_external_trigger",
            ],
            "pending": [
                "34460A DCV Ratio live validation",
                "LAN/TCPIP system-VISA validation",
                "LAN/TCPIP pyvisa-py @py validation",
            ],
            "pending_keys": [
                "support.pending.keysight_34460a_dcv_ratio_live_validation",
                "support.pending.lan_tcpip_system_visa_validation",
                "support.pending.lan_tcpip_pyvisa_py_validation",
            ],
        }
    if profile.model == "34461A":
        return {
            **common,
            "model": "34461A",
            "validation_status": live_support.validation_status,
            "transport_scope": live_support.transport_scope,
            "backend_scope": live_support.backend_scope,
            "status_text": (
                "Full-suite validated for profile-supported workflows on "
                "USB/system-VISA, LAN/system-VISA, and optional CLI-only LAN/pyvisa-py @py."
            ),
            "status_key": "support.status.profile_workflows_validated",
            "open_workflows": [
                "immediate",
                "software",
                "software timer",
                "custom buffered",
                "Frequency",
                "Period",
                "external trigger workflows",
            ],
            "open_workflow_keys": [
                "support.workflow.immediate",
                "support.workflow.software",
                "support.workflow.software_timer",
                "support.workflow.custom_buffered",
                "support.workflow.frequency",
                "support.workflow.period",
                "support.workflow.external_trigger",
            ],
            "limits": [],
            "limit_keys": [],
            "pending": [],
            "pending_keys": [],
        }
    return {
        **common,
        "model": profile.model,
        "validation_status": live_support.validation_status,
        "transport_scope": live_support.transport_scope,
        "backend_scope": live_support.backend_scope,
        "status_text": "Live support is not open for this profile.",
        "status_key": "support.status.not_open",
        "open_workflows": [],
        "open_workflow_keys": [],
        "limits": [],
        "limit_keys": [],
        "pending": [],
        "pending_keys": [],
    }


def support_scope_payload(scope: Any) -> dict[str, Any]:
    payload = {
        "validation_status": scope.validation_status,
        "transport_scope": scope.transport_scope,
        "backend_scope": scope.backend_scope,
        "features": support_features_payload(scope),
    }
    if getattr(scope, "evidence", None):
        payload["evidence"] = scope.evidence
    if getattr(scope, "artifact", None):
        payload["artifact"] = scope.artifact
    if getattr(scope, "note", None):
        payload["note"] = scope.note
    return payload


def support_features_payload(scope: Any) -> dict[str, dict[str, dict[str, Any]]]:
    features: dict[str, dict[str, dict[str, Any]]] = {
        FEATURE_KIND_MEASUREMENT: {},
        FEATURE_KIND_TRIGGER_MODE: {},
    }
    for feature in getattr(scope, "feature_scopes", ()):
        feature_kind = feature.feature_kind
        feature_value = (
            format_measurement_type(feature.feature_value)
            if feature_kind == FEATURE_KIND_MEASUREMENT
            else feature.feature_value
        )
        feature_payload = {"validation_status": feature.validation_status}
        if feature.evidence:
            feature_payload["evidence"] = feature.evidence
        if feature.artifact:
            feature_payload["artifact"] = feature.artifact
        if feature.note:
            feature_payload["note"] = feature.note
        features.setdefault(feature_kind, {})[feature_value] = feature_payload
    return features


def sample_payload(sample: Any, sequence: int) -> dict[str, Any] | None:
    if sample is None:
        return None
    timestamp_utc = getattr(sample, "timestamp_utc", None)
    if hasattr(timestamp_utc, "astimezone"):
        timestamp_text = timestamp_utc.astimezone(UTC_PLUS_8).isoformat()
    elif timestamp_utc is None:
        timestamp_text = None
    else:
        timestamp_text = str(timestamp_utc)
    return {
        "sequence": sequence,
        "timestamp_utc_plus_8": timestamp_text,
        "measurement_type": getattr(sample, "measurement_type", None),
        "value": getattr(sample, "value", None),
        "unit": getattr(sample, "unit", None),
        "trigger_id": getattr(sample, "trigger_id", None),
        "trigger_source": getattr(sample, "trigger_source", None),
        "trigger_metadata": json_safe_mapping(getattr(sample, "trigger_metadata", {})),
        "measurement_metadata": json_safe_mapping(
            getattr(sample, "measurement_metadata", {})
        ),
        "resource_id": getattr(sample, "resource_id", None),
        "status": getattr(sample, "status", None),
    }


def json_safe_mapping(value: Any) -> dict[str, Any]:
    safe_value = json_safe_value(value or {})
    return safe_value if isinstance(safe_value, dict) else {}


def json_safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): json_safe_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe_value(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def range_limit(
    value_range: tuple[float, float] | tuple[int, int],
) -> dict[str, float | int]:
    return {"min": value_range[0], "max": value_range[1]}
