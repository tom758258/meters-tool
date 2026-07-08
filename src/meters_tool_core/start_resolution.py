from __future__ import annotations

from dataclasses import replace

from .instrument import VisaInstrument
from .models import (
    INSTRUMENT_PROFILES,
    InstrumentProfile,
    StartRequest,
    find_instrument_profile_by_idn,
    find_instrument_profile_by_model,
    normalize_requested_model,
    supported_instrument_models,
)


def _supported_model_option_hint() -> str:
    return " or ".join(f"--model {model}" for model in supported_instrument_models())


def _supported_sim_resource_hint() -> str:
    return " / ".join(f"SIM::{model}" for model in supported_instrument_models())


DRY_RUN_AUTO_MODEL_ERROR = (
    "dry-run cannot auto-detect the instrument model without VISA I/O; "
    f"pass {_supported_model_option_hint()}."
)
SIMULATE_AUTO_MODEL_ERROR = (
    "simulate cannot auto-detect the instrument model unless the simulator resource encodes it; "
    f"pass {_supported_model_option_hint()}, or use {_supported_sim_resource_hint()}."
)


def infer_simulator_profile(resource: str) -> InstrumentProfile | None:
    text = str(resource).strip().upper()
    if not text.startswith("SIM::"):
        return None
    matches = [
        profile
        for profile in INSTRUMENT_PROFILES
        if text.count(profile.model.upper()) == 1
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def resolve_start_profile(request: StartRequest) -> tuple[StartRequest, InstrumentProfile]:
    if request.dry_run and request.simulate:
        raise ValueError("--dry-run and --simulate cannot be used together")
    requested_model = normalize_requested_model(request.instrument_model)
    normalized_request = replace(request, instrument_model=requested_model)
    if requested_model is not None:
        requested_profile = find_instrument_profile_by_model(requested_model)
        if request.dry_run or request.simulate:
            return normalized_request, requested_profile
        idn = VisaInstrument.preflight_idn(
            request.resource,
            timeout_ms=request.timeout_ms,
            visa_library=request.visa_library,
        )
        connected_profile = find_instrument_profile_by_idn(idn)
        if connected_profile.model != requested_profile.model:
            raise ValueError(
                f"Selected model {requested_profile.model} does not match the connected "
                f"instrument IDN {connected_profile.model}. Select {connected_profile.model} "
                "or omit --model to auto-detect."
            )
        return normalized_request, requested_profile

    if request.dry_run:
        inferred = infer_simulator_profile(request.resource)
        if inferred is None:
            raise ValueError(DRY_RUN_AUTO_MODEL_ERROR)
        return replace(normalized_request, instrument_model=inferred.model), inferred

    if request.simulate:
        inferred = infer_simulator_profile(request.resource)
        if inferred is None:
            raise ValueError(SIMULATE_AUTO_MODEL_ERROR)
        return replace(normalized_request, instrument_model=inferred.model), inferred

    idn = VisaInstrument.preflight_idn(
        request.resource,
        timeout_ms=request.timeout_ms,
        visa_library=request.visa_library,
    )
    connected_profile = find_instrument_profile_by_idn(idn)
    return replace(normalized_request, instrument_model=connected_profile.model), connected_profile
