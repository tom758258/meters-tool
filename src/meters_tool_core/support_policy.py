from __future__ import annotations

from dataclasses import dataclass

from .measurement import normalize_measurement_type
from .models import InstrumentProfile, StartRequest


VALIDATION_STATUS_NOT_SUPPORTED_BY_MODEL = "not_supported_by_model"
VALIDATION_STATUS_PROFILE_VALIDATED = "profile_validated"
VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE = "live_validated_full_suite"
VALIDATION_STATUS_TRANSPORT_PENDING = "transport_pending"

TRANSPORT_USB = "usb"
TRANSPORT_TCPIP = "tcpip"
TRANSPORT_UNKNOWN = "unknown"
BACKEND_SYSTEM_VISA = "system_visa"
BACKEND_PYVISA_PY = "pyvisa_py"
BACKEND_CUSTOM = "custom_visa"


@dataclass(frozen=True)
class StartWorkflowSupportScope:
    validation_status: str
    transport_scope: str
    backend_scope: str
    evidence: str | None = None
    artifact: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class StartWorkflowSupport:
    validation_status: str
    transport_scope: str | None = None
    backend_scope: str | None = None
    scopes: tuple[StartWorkflowSupportScope, ...] = ()


def start_workflow_support(profile: InstrumentProfile) -> dict[str, dict[str, StartWorkflowSupport]]:
    if profile.model == "34461A":
        live_scopes = (
            StartWorkflowSupportScope(
                VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE,
                TRANSPORT_USB,
                BACKEND_SYSTEM_VISA,
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
            ),
            StartWorkflowSupportScope(
                VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE,
                TRANSPORT_TCPIP,
                BACKEND_PYVISA_PY,
                evidence="operator_full_suite",
                artifact=".tmp_tests/cli_live/keysight-34461a/lan/full/20260709-112406/summary.md",
                note="Optional CLI-only pyvisa-py @py backend validation.",
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
            ),
            StartWorkflowSupportScope(
                VALIDATION_STATUS_TRANSPORT_PENDING,
                TRANSPORT_TCPIP,
                BACKEND_SYSTEM_VISA,
                note="Pending a LAN/LXI-enabled 34460A TCPIP resource and validation artifact.",
            ),
            StartWorkflowSupportScope(
                VALIDATION_STATUS_TRANSPORT_PENDING,
                TRANSPORT_TCPIP,
                BACKEND_PYVISA_PY,
                note="Pending a LAN/LXI-enabled 34460A TCPIP resource and validation artifact.",
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
) -> None:
    effective_mode = mode or _start_mode(request)
    if effective_mode in {"dry_run", "simulate"}:
        return
    if effective_mode != "live":
        raise ValueError(f"unsupported start workflow mode: {effective_mode}")

    effective_transport = transport_scope or infer_transport_scope(request.resource)
    effective_backend = backend_scope or infer_backend_scope(request.visa_library)
    measurement_type = normalize_measurement_type(request.measurement)

    if detected_profile.model not in {"34460A", "34461A"}:
        raise ValueError(
            f"start-trigger-record live is not supported by {detected_profile.model}"
        )

    live_support = start_workflow_support(detected_profile)["start-trigger-record"]["live"]
    scope_support = _find_scope_support(live_support, effective_transport, effective_backend)
    if (
        scope_support is None
        or scope_support.validation_status != VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE
    ):
        raise ValueError(
            f"{detected_profile.model} live support for start-trigger-record is not open for "
            f"transport={effective_transport}, backend={effective_backend} is pending."
        )
    if detected_profile.model == "34461A":
        return
    if trigger_mode in {"external", "external-custom"}:
        raise ValueError(
            f"34460A live support for --trigger-mode {trigger_mode} is not open; "
            "the base 34460A profile does not support external trigger workflows."
        )
    if measurement_type == "voltage_dc_ratio":
        raise ValueError(
            "34460A live support for --measurement voltage-dc-ratio is not validated; "
            "34460A DCV Ratio remains closed unless separately validated."
        )


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
