from __future__ import annotations

import csv
from contextlib import ExitStack
from dataclasses import dataclass
from typing import Callable, Literal

from .instrument import InstrumentError, _create_resource_manager
from .models import (
    InstrumentConfig,
    find_instrument_profile_by_idn,
    find_instrument_profile_by_model,
    normalize_requested_model,
)
from .simulator import SimulatedVisaInstrument
from .start_resolution import infer_simulator_profile
from .support_policy import validate_product_live_connection


DEFAULT_MAX_READS = 20
ErrorQueueMode = Literal["real", "simulate", "dry-run"]
ErrorQueueTermination = Literal["no_error", "max_reads", "dry_run", "failed"]


@dataclass(frozen=True)
class ScpiError:
    code: int
    message: str


@dataclass(frozen=True)
class ErrorQueueResult:
    mode: ErrorQueueMode
    model: str
    max_reads: int
    reads: int
    termination: ErrorQueueTermination
    queue_cleared: bool
    errors: tuple[ScpiError, ...]


class ErrorQueueReadError(InstrumentError):
    def __init__(self, message: str, partial_result: ErrorQueueResult):
        super().__init__(message)
        self.partial_result = partial_result


def _parse_scpi_error(reply: str) -> ScpiError:
    code_text, separator, message = reply.strip().partition(",")
    message = message.strip()
    try:
        code = int(code_text)
        if code == 0 and not separator:
            return ScpiError(code, "")
        if not separator or not message:
            raise ValueError
        if message.startswith('"'):
            (message,) = next(csv.reader([message], strict=True))
        return ScpiError(code, message)
    except (ValueError, csv.Error) as exc:
        raise InstrumentError(f"invalid SYST:ERR? response: {reply!r}") from exc


def read_error_queue(
    resource: str = "",
    *,
    visa_library: str | None = None,
    instrument_model: str | None = None,
    max_reads: int = DEFAULT_MAX_READS,
    mode: ErrorQueueMode = "real",
    resource_manager_factory: Callable[[], object] | None = None,
) -> ErrorQueueResult:
    """Consume up to max_reads queue replies using a dedicated diagnostic session."""
    if type(max_reads) is not int or max_reads < 1:
        raise ValueError("max_reads must be a positive integer")
    if mode not in {"real", "simulate", "dry-run"}:
        raise ValueError(f"unsupported error queue mode: {mode}")
    resource = resource.strip()
    visa_library = (visa_library or "").strip().lower() or None
    expected_model = normalize_requested_model(instrument_model)
    expected_profile = (
        find_instrument_profile_by_model(expected_model) if expected_model else None
    )
    if mode == "real":
        if not resource:
            raise ValueError("a VISA resource is required to read the live error queue")
        validate_product_live_connection(resource, visa_library, expected_profile)
    else:
        profile = expected_profile or infer_simulator_profile(resource)
        if profile is None:
            raise ValueError(f"{mode} requires a supported model or a model-specific simulator resource")
        if mode == "dry-run":
            return ErrorQueueResult(mode, profile.model, max_reads, 0, "dry_run", False, ())
        expected_model = profile.model
        resource = f"SIM::{profile.model}"

    config = InstrumentConfig(resource, expected_model=expected_model, visa_library=visa_library)
    detected_model = None
    reads = 0
    errors: list[ScpiError] = []
    try:
        with ExitStack() as stack:
            if mode == "simulate":
                instrument = SimulatedVisaInstrument(config)
            else:
                manager = (
                    resource_manager_factory() if resource_manager_factory is not None
                    else _create_resource_manager(visa_library)
                )
                stack.callback(manager.close)
                instrument = manager.open_resource(resource)
            stack.callback(instrument.close)
            if mode == "real":
                instrument.timeout = config.timeout_ms
            detected = find_instrument_profile_by_idn(str(instrument.query("*IDN?")).strip())
            if expected_model is not None and detected.model != expected_model:
                raise ValueError(
                    f"Selected model {expected_model} does not match the connected instrument "
                    f"IDN {detected.model}"
                )
            if mode == "real":
                validate_product_live_connection(resource, visa_library, detected)
            detected_model = detected.model
            while reads < max_reads:
                entry = _parse_scpi_error(str(instrument.query("SYST:ERR?")))
                reads += 1
                if entry.code == 0:
                    return ErrorQueueResult(
                        mode, detected_model, max_reads, reads, "no_error", True, tuple(errors)
                    )
                errors.append(entry)
            return ErrorQueueResult(
                mode, detected_model, max_reads, reads, "max_reads", False, tuple(errors)
            )
    except Exception as exc:
        if not errors and isinstance(exc, (ValueError, InstrumentError)):
            raise
        message = (
            str(exc) if isinstance(exc, InstrumentError) else f"failed to read SCPI error queue: {exc}"
        )
        if errors and detected_model is not None:
            partial_result = ErrorQueueResult(
                mode, detected_model, max_reads, reads, "failed", False, tuple(errors)
            )
            raise ErrorQueueReadError(message, partial_result) from exc
        raise InstrumentError(message) from exc
