from __future__ import annotations

from dataclasses import dataclass

from .measurement import format_measurement_type, normalize_measurement_type
from .models import InstrumentProfile, StartRequest
from .validation import resolve_trigger_mode, supported_measurement_types, supported_trigger_modes


FEATURE_KIND_MEASUREMENT = "measurement"
FEATURE_KIND_TRIGGER_MODE = "trigger_mode"

VALIDATION_STATUS_NOT_SUPPORTED_BY_MODEL = "not_supported_by_model"
VALIDATION_STATUS_PROFILE_VALIDATED = "profile_validated"
VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE = "live_validated_full_suite"
VALIDATION_STATUS_TRANSPORT_PENDING = "transport_pending"
VALIDATION_STATUS_FEATURE_PENDING = "feature_pending"

SUPPORT_POLICY_MODE_PRODUCT = "product"
SUPPORT_POLICY_MODE_VALIDATION = "validation"

TRANSPORT_USB = "usb"
TRANSPORT_TCPIP = "tcpip"
TRANSPORT_UNKNOWN = "unknown"
BACKEND_SYSTEM_VISA = "system_visa"
BACKEND_PYVISA_PY = "pyvisa_py"
BACKEND_CUSTOM = "custom_visa"


@dataclass(frozen=True)
class StartFeatureSupportScope:
    feature_kind: str
    feature_value: str
    validation_status: str
    evidence: str | None = None
    artifact: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class StartWorkflowSupportScope:
    validation_status: str
    transport_scope: str
    backend_scope: str
    evidence: str | None = None
    artifact: str | None = None
    note: str | None = None
    feature_scopes: tuple[StartFeatureSupportScope, ...] = ()


@dataclass(frozen=True)
class StartWorkflowSupport:
    validation_status: str
    transport_scope: str | None = None
    backend_scope: str | None = None
    scopes: tuple[StartWorkflowSupportScope, ...] = ()


_FEATURE_STATUSES_34461A_MEASUREMENTS = (
    ("current_dc", VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE),
    ("current_ac", VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE),
    ("voltage_dc", VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE),
    ("voltage_ac", VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE),
    ("voltage_dc_ratio", VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE),
    ("frequency", VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE),
    ("period", VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE),
    ("resistance_2w", VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE),
    ("resistance_4w", VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE),
)
_FEATURE_STATUSES_34461A_TRIGGER_MODES = (
    ("software", VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE),
    ("immediate", VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE),
    ("external", VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE),
    ("immediate-custom", VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE),
    ("software-custom", VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE),
    ("external-custom", VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE),
)
_FEATURE_STATUSES_34460A_USB_MEASUREMENTS = (
    ("current_dc", VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE),
    ("current_ac", VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE),
    ("voltage_dc", VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE),
    ("voltage_ac", VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE),
    ("voltage_dc_ratio", VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE),
    ("frequency", VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE),
    ("period", VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE),
    ("resistance_2w", VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE),
    ("resistance_4w", VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE),
)
_FEATURE_STATUSES_34460A_USB_TRIGGER_MODES = (
    ("software", VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE),
    ("immediate", VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE),
    ("immediate-custom", VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE),
    ("software-custom", VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE),
)
_FEATURE_STATUSES_34460A_PENDING_MEASUREMENTS = (
    ("current_dc", VALIDATION_STATUS_FEATURE_PENDING),
    ("current_ac", VALIDATION_STATUS_FEATURE_PENDING),
    ("voltage_dc", VALIDATION_STATUS_FEATURE_PENDING),
    ("voltage_ac", VALIDATION_STATUS_FEATURE_PENDING),
    ("voltage_dc_ratio", VALIDATION_STATUS_FEATURE_PENDING),
    ("frequency", VALIDATION_STATUS_FEATURE_PENDING),
    ("period", VALIDATION_STATUS_FEATURE_PENDING),
    ("resistance_2w", VALIDATION_STATUS_FEATURE_PENDING),
    ("resistance_4w", VALIDATION_STATUS_FEATURE_PENDING),
)
_FEATURE_STATUSES_34460A_PENDING_TRIGGER_MODES = (
    ("software", VALIDATION_STATUS_FEATURE_PENDING),
    ("immediate", VALIDATION_STATUS_FEATURE_PENDING),
    ("immediate-custom", VALIDATION_STATUS_FEATURE_PENDING),
    ("software-custom", VALIDATION_STATUS_FEATURE_PENDING),
)


def _feature_scopes(
    measurement_statuses: tuple[tuple[str, str], ...],
    trigger_mode_statuses: tuple[tuple[str, str], ...],
) -> tuple[StartFeatureSupportScope, ...]:
    return tuple(
        StartFeatureSupportScope(FEATURE_KIND_MEASUREMENT, value, status)
        for value, status in measurement_statuses
    ) + tuple(
        StartFeatureSupportScope(FEATURE_KIND_TRIGGER_MODE, value, status)
        for value, status in trigger_mode_statuses
    )


def start_workflow_support(profile: InstrumentProfile) -> dict[str, dict[str, StartWorkflowSupport]]:
    if profile.model == "34461A":
        live_scopes = (
            StartWorkflowSupportScope(
                VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE,
                TRANSPORT_USB,
                BACKEND_SYSTEM_VISA,
                feature_scopes=_feature_scopes(
                    _FEATURE_STATUSES_34461A_MEASUREMENTS,
                    _FEATURE_STATUSES_34461A_TRIGGER_MODES,
                ),
            ),
            StartWorkflowSupportScope(
                VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE,
                TRANSPORT_TCPIP,
                BACKEND_SYSTEM_VISA,
                evidence="reviewed_artifact_correction",
                artifact=".tmp_tests/cli_live/keysight-34461a/usb/Full/20260708-211944/summary.md",
                note=(
                    "Full suite used a TCPIP resource through system VISA; "
                    "the wrapper connection label was corrected from usb to lan."
                ),
                feature_scopes=_feature_scopes(
                    _FEATURE_STATUSES_34461A_MEASUREMENTS,
                    _FEATURE_STATUSES_34461A_TRIGGER_MODES,
                ),
            ),
            StartWorkflowSupportScope(
                VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE,
                TRANSPORT_TCPIP,
                BACKEND_PYVISA_PY,
                evidence="operator_full_suite",
                artifact=".tmp_tests/cli_live/keysight-34461a/lan/full/20260709-112406/summary.md",
                note="Optional CLI-only pyvisa-py @py backend validation.",
                feature_scopes=_feature_scopes(
                    _FEATURE_STATUSES_34461A_MEASUREMENTS,
                    _FEATURE_STATUSES_34461A_TRIGGER_MODES,
                ),
            ),
        )
        return {
            "start-trigger-record": {
                "dry_run": StartWorkflowSupport(VALIDATION_STATUS_PROFILE_VALIDATED),
                "simulate": StartWorkflowSupport(VALIDATION_STATUS_PROFILE_VALIDATED),
                "live": StartWorkflowSupport(
                    VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE,
                    transport_scope=TRANSPORT_USB,
                    backend_scope=BACKEND_SYSTEM_VISA,
                    scopes=live_scopes,
                ),
            }
        }
    if profile.model == "34460A":
        live_scopes = (
            StartWorkflowSupportScope(
                VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE,
                TRANSPORT_USB,
                BACKEND_SYSTEM_VISA,
                feature_scopes=_feature_scopes(
                    _FEATURE_STATUSES_34460A_USB_MEASUREMENTS,
                    _FEATURE_STATUSES_34460A_USB_TRIGGER_MODES,
                ),
            ),
            StartWorkflowSupportScope(
                VALIDATION_STATUS_TRANSPORT_PENDING,
                TRANSPORT_TCPIP,
                BACKEND_SYSTEM_VISA,
                note="Pending a LAN/LXI-enabled 34460A TCPIP resource and validation artifact.",
                feature_scopes=_feature_scopes(
                    _FEATURE_STATUSES_34460A_PENDING_MEASUREMENTS,
                    _FEATURE_STATUSES_34460A_PENDING_TRIGGER_MODES,
                ),
            ),
            StartWorkflowSupportScope(
                VALIDATION_STATUS_TRANSPORT_PENDING,
                TRANSPORT_TCPIP,
                BACKEND_PYVISA_PY,
                note="Pending a LAN/LXI-enabled 34460A TCPIP resource and validation artifact.",
                feature_scopes=_feature_scopes(
                    _FEATURE_STATUSES_34460A_PENDING_MEASUREMENTS,
                    _FEATURE_STATUSES_34460A_PENDING_TRIGGER_MODES,
                ),
            ),
        )
        return {
            "start-trigger-record": {
                "dry_run": StartWorkflowSupport(VALIDATION_STATUS_PROFILE_VALIDATED),
                "simulate": StartWorkflowSupport(VALIDATION_STATUS_PROFILE_VALIDATED),
                "live": StartWorkflowSupport(
                    VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE,
                    transport_scope=TRANSPORT_USB,
                    backend_scope=BACKEND_SYSTEM_VISA,
                    scopes=live_scopes,
                ),
            }
        }
    return {
        "start-trigger-record": {
            "dry_run": StartWorkflowSupport(VALIDATION_STATUS_PROFILE_VALIDATED),
            "simulate": StartWorkflowSupport(VALIDATION_STATUS_PROFILE_VALIDATED),
            "live": StartWorkflowSupport(VALIDATION_STATUS_NOT_SUPPORTED_BY_MODEL),
        }
    }


def normalize_support_feature_value(feature_kind: str, feature_value: str) -> str:
    normalized_kind = str(feature_kind).strip().lower().replace("-", "_")
    if normalized_kind == FEATURE_KIND_MEASUREMENT:
        return normalize_measurement_type(feature_value)
    if normalized_kind == FEATURE_KIND_TRIGGER_MODE:
        return str(feature_value).strip().lower().replace("_", "-")
    raise ValueError(f"unsupported support feature kind: {feature_kind}")


def start_request_feature_requirements(
    request: StartRequest,
) -> tuple[tuple[str, str], ...]:
    return (
        (
            FEATURE_KIND_MEASUREMENT,
            normalize_support_feature_value(FEATURE_KIND_MEASUREMENT, request.measurement),
        ),
        (
            FEATURE_KIND_TRIGGER_MODE,
            normalize_support_feature_value(
                FEATURE_KIND_TRIGGER_MODE,
                resolve_trigger_mode(request),
            ),
        ),
    )


def find_feature_support(
    scope: StartWorkflowSupportScope,
    feature_kind: str,
    feature_value: str,
) -> StartFeatureSupportScope | None:
    normalized_kind = str(feature_kind).strip().lower().replace("-", "_")
    normalized_value = normalize_support_feature_value(normalized_kind, feature_value)
    matches = [
        feature
        for feature in scope.feature_scopes
        if feature.feature_kind == normalized_kind and feature.feature_value == normalized_value
    ]
    if len(matches) > 1:
        raise ValueError(
            "duplicate live feature support registration for "
            f"{normalized_kind}={normalized_value}, "
            f"transport={scope.transport_scope}, backend={scope.backend_scope}"
        )
    return matches[0] if matches else None


def infer_transport_scope(resource: str) -> str:
    text = str(resource).strip().upper()
    if text.startswith("USB"):
        return TRANSPORT_USB
    if text.startswith("TCPIP"):
        return TRANSPORT_TCPIP
    return TRANSPORT_UNKNOWN


def infer_backend_scope(visa_library: str | None) -> str:
    if visa_library is None or not str(visa_library).strip():
        return BACKEND_SYSTEM_VISA
    if str(visa_library).strip().lower() == "@py":
        return BACKEND_PYVISA_PY
    return BACKEND_CUSTOM


def validate_start_workflow_support(
    request: StartRequest,
    trigger_mode: str,
    detected_profile: InstrumentProfile,
    mode: str | None = None,
    *,
    transport_scope: str | None = None,
    backend_scope: str | None = None,
    support_policy_mode: str = SUPPORT_POLICY_MODE_PRODUCT,
) -> None:
    if support_policy_mode not in {
        SUPPORT_POLICY_MODE_PRODUCT,
        SUPPORT_POLICY_MODE_VALIDATION,
    }:
        raise ValueError(f"unsupported support policy mode: {support_policy_mode}")

    effective_mode = mode or _start_mode(request)
    if effective_mode in {"dry_run", "simulate"}:
        return
    if effective_mode != "live":
        raise ValueError(f"unsupported start workflow mode: {effective_mode}")

    effective_transport = transport_scope or infer_transport_scope(request.resource)
    effective_backend = backend_scope or infer_backend_scope(request.visa_library)

    if detected_profile.model not in {"34460A", "34461A"}:
        raise ValueError(
            f"start-trigger-record live is not supported by {detected_profile.model}"
        )

    live_support = start_workflow_support(detected_profile)["start-trigger-record"]["live"]
    scope_support = _find_scope_support(live_support, effective_transport, effective_backend)
    _validate_connection_scope_support(
        detected_profile,
        scope_support,
        effective_transport,
        effective_backend,
        support_policy_mode,
    )
    assert scope_support is not None

    # `trigger_mode` is retained for public API compatibility. Core derives the
    # effective feature requirement from the resolved request.
    _ = trigger_mode
    for feature_kind, feature_value in start_request_feature_requirements(request):
        feature_support = find_feature_support(scope_support, feature_kind, feature_value)
        _validate_feature_scope_support(
            detected_profile,
            scope_support,
            feature_kind,
            feature_value,
            feature_support,
            support_policy_mode,
        )


def validate_start_workflow_support_metadata(
    profile: InstrumentProfile,
    support: StartWorkflowSupport | None = None,
) -> None:
    live_support = support or start_workflow_support(profile)["start-trigger-record"]["live"]
    expected = {
        FEATURE_KIND_MEASUREMENT: {
            normalize_support_feature_value(FEATURE_KIND_MEASUREMENT, value)
            for value in supported_measurement_types(profile)
        },
        FEATURE_KIND_TRIGGER_MODE: {
            normalize_support_feature_value(FEATURE_KIND_TRIGGER_MODE, value)
            for value in supported_trigger_modes(profile)
        },
    }
    allowed_connection_statuses = {
        VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE,
        VALIDATION_STATUS_TRANSPORT_PENDING,
        VALIDATION_STATUS_NOT_SUPPORTED_BY_MODEL,
    }
    allowed_feature_statuses = {
        VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE,
        VALIDATION_STATUS_FEATURE_PENDING,
        VALIDATION_STATUS_NOT_SUPPORTED_BY_MODEL,
    }
    seen_scopes: set[tuple[str, str]] = set()

    for scope in live_support.scopes:
        scope_key = (scope.transport_scope, scope.backend_scope)
        if scope_key in seen_scopes:
            raise ValueError(
                "duplicate live connection support registration for "
                f"transport={scope.transport_scope}, backend={scope.backend_scope}"
            )
        seen_scopes.add(scope_key)
        if scope.validation_status not in allowed_connection_statuses:
            raise ValueError(
                f"unsupported connection validation status: {scope.validation_status}"
            )

        seen_features = {
            FEATURE_KIND_MEASUREMENT: set(),
            FEATURE_KIND_TRIGGER_MODE: set(),
        }
        for feature in scope.feature_scopes:
            if feature.feature_kind not in seen_features:
                raise ValueError(f"unsupported support feature kind: {feature.feature_kind}")
            normalized_value = normalize_support_feature_value(
                feature.feature_kind,
                feature.feature_value,
            )
            if feature.feature_value != normalized_value:
                raise ValueError(
                    "live feature support value is not normalized for "
                    f"{feature.feature_kind}={feature.feature_value}"
                )
            if feature.feature_value in seen_features[feature.feature_kind]:
                raise ValueError(
                    "duplicate live feature support registration for "
                    f"{feature.feature_kind}={feature.feature_value}, "
                    f"transport={scope.transport_scope}, backend={scope.backend_scope}"
                )
            if feature.validation_status not in allowed_feature_statuses:
                raise ValueError(
                    f"unsupported feature validation status: {feature.validation_status}"
                )
            seen_features[feature.feature_kind].add(feature.feature_value)

        for feature_kind, expected_values in expected.items():
            actual_values = seen_features[feature_kind]
            missing = sorted(expected_values - actual_values)
            unexpected = sorted(actual_values - expected_values)
            if missing or unexpected:
                detail = []
                if missing:
                    detail.append(f"missing={','.join(missing)}")
                if unexpected:
                    detail.append(f"unexpected={','.join(unexpected)}")
                raise ValueError(
                    f"{profile.model} {feature_kind} support inventory mismatch for "
                    f"transport={scope.transport_scope}, backend={scope.backend_scope}: "
                    + "; ".join(detail)
                )


def _validate_connection_scope_support(
    profile: InstrumentProfile,
    scope_support: StartWorkflowSupportScope | None,
    transport_scope: str,
    backend_scope: str,
    support_policy_mode: str,
) -> None:
    if scope_support is None:
        raise ValueError(
            f"{profile.model} live support for start-trigger-record is not registered for "
            f"transport={transport_scope}, backend={backend_scope}"
        )
    status = scope_support.validation_status
    if status == VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE:
        return
    if status == VALIDATION_STATUS_TRANSPORT_PENDING:
        if support_policy_mode == SUPPORT_POLICY_MODE_VALIDATION:
            return
        raise ValueError(
            f"{profile.model} live support for start-trigger-record is pending for "
            f"transport={transport_scope}, backend={backend_scope}"
        )
    if status == VALIDATION_STATUS_NOT_SUPPORTED_BY_MODEL:
        raise ValueError(
            f"{profile.model} live support for start-trigger-record is not supported by the "
            f"detected model for transport={transport_scope}, backend={backend_scope}"
        )
    raise ValueError(
        f"{profile.model} live support for start-trigger-record has unknown validation status "
        f"{status!r} for transport={transport_scope}, backend={backend_scope}"
    )


def _validate_feature_scope_support(
    profile: InstrumentProfile,
    connection_scope: StartWorkflowSupportScope,
    feature_kind: str,
    feature_value: str,
    feature_support: StartFeatureSupportScope | None,
    support_policy_mode: str,
) -> None:
    feature_label, display_value = _format_feature_requirement(feature_kind, feature_value)
    scope_text = (
        f"transport={connection_scope.transport_scope}, "
        f"backend={connection_scope.backend_scope}"
    )
    if feature_support is None:
        raise ValueError(
            f"{profile.model} live feature support is not registered for "
            f"{feature_label}={display_value}, {scope_text}"
        )
    status = feature_support.validation_status
    if status == VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE:
        return
    if status == VALIDATION_STATUS_FEATURE_PENDING:
        if support_policy_mode == SUPPORT_POLICY_MODE_VALIDATION:
            return
        raise ValueError(
            f"{profile.model} live support for {feature_label}={display_value} is pending "
            f"validation for {scope_text}"
        )
    if status == VALIDATION_STATUS_NOT_SUPPORTED_BY_MODEL:
        raise ValueError(
            f"{feature_label}={display_value} is not supported by the detected "
            f"{profile.model} profile for {scope_text}"
        )
    raise ValueError(
        f"{profile.model} live feature support has unknown validation status {status!r} for "
        f"{feature_label}={display_value}, {scope_text}"
    )


def _format_feature_requirement(feature_kind: str, feature_value: str) -> tuple[str, str]:
    if feature_kind == FEATURE_KIND_MEASUREMENT:
        return "measurement", format_measurement_type(feature_value)
    if feature_kind == FEATURE_KIND_TRIGGER_MODE:
        return "trigger-mode", feature_value
    return feature_kind.replace("_", "-"), feature_value


def _start_mode(request: StartRequest) -> str:
    if request.dry_run:
        return "dry_run"
    if request.simulate:
        return "simulate"
    return "live"


def _find_scope_support(
    support: StartWorkflowSupport,
    transport_scope: str,
    backend_scope: str,
) -> StartWorkflowSupportScope | None:
    for scope in support.scopes:
        if scope.transport_scope == transport_scope and scope.backend_scope == backend_scope:
            return scope
    if (
        support.transport_scope == transport_scope
        and support.backend_scope == backend_scope
    ):
        return StartWorkflowSupportScope(
            support.validation_status,
            transport_scope,
            backend_scope,
        )
    return None
