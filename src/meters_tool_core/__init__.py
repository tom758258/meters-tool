"""Minimal public API for core start-request orchestration."""

from .capabilities import CoreCapabilities, MeasurementCapability, get_core_capabilities
from .models import (
    InstrumentProfile,
    StartRequest,
    get_default_instrument_profile,
    resolve_instrument_profile,
)
from .run_plan import StartPlan, build_start_plan
from .runner import run_start_session
from .session import (
    NoOpControlPlane,
    StartControlPlane,
    StartControlPlaneHandle,
    StartRunEvent,
    StartRunEventSink,
    StartRunResult,
    StopController,
)
from .validation import (
    CoreWarning,
    generate_buffer_overflow_warning_details,
    generate_buffer_overflow_warnings,
    resolve_trigger_mode,
    validate_start_request,
)

__all__ = [
    "MeasurementCapability",
    "CoreCapabilities",
    "get_core_capabilities",
    "CoreWarning",
    "InstrumentProfile",
    "StartRequest",
    "get_default_instrument_profile",
    "resolve_instrument_profile",
    "StartPlan",
    "build_start_plan",
    "generate_buffer_overflow_warning_details",
    "generate_buffer_overflow_warnings",
    "resolve_trigger_mode",
    "validate_start_request",
    "StartRunEvent",
    "StartRunEventSink",
    "StartRunResult",
    "StartControlPlane",
    "StartControlPlaneHandle",
    "NoOpControlPlane",
    "StopController",
    "run_start_session",
]
