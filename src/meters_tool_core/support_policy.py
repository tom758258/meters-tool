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
class StartWorkflowSupport:
    validation_status: str
    transport_scope: str | None = None
    backend_scope: str | None = None


def start_workflow_support(profile: InstrumentProfile) -> dict[str, dict[str, StartWorkflowSupport]]:
    if profile.model in {"34460A", "34461A"}:
        return {
            "start-trigger-record": {
                "dry_run": StartWorkflowSupport(VALIDATION_STATUS_PROFILE_VALIDATED),
                "simulate": StartWorkflowSupport(VALIDATION_STATUS_PROFILE_VALIDATED),
                "live": StartWorkflowSupport(
                    VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE,
                    transport_scope=TRANSPORT_USB,
                    backend_scope=BACKEND_SYSTEM_VISA,
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

    if detected_profile.model == "34461A":
        return
    if detected_profile.model != "34460A":
        raise ValueError(
            f"start-trigger-record live is not supported by {detected_profile.model}"
        )

    if effective_transport != TRANSPORT_USB or effective_backend != BACKEND_SYSTEM_VISA:
        raise ValueError(
            "34460A live support for start-trigger-record is validated only for "
            "usb/system_visa; "
            f"transport={effective_transport}, backend={effective_backend} is pending."
        )
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
