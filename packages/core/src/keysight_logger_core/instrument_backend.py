from __future__ import annotations

from typing import Callable, Protocol, runtime_checkable

from .instrument import VisaInstrument
from .models import InstrumentConfig
from .simulator import SimulatedVisaInstrument


@runtime_checkable
class InstrumentBackend(Protocol):
    @property
    def resource_id(self) -> str:
        raise NotImplementedError

    def connect(self) -> None:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError

    def write(self, command: str) -> None:
        raise NotImplementedError

    def query(self, command: str) -> str:
        raise NotImplementedError

    def query_ascii_float(self, command: str) -> float:
        raise NotImplementedError

    def read_status_byte(self) -> int:
        raise NotImplementedError

    def set_timeout_ms(self, timeout_ms: int) -> None:
        raise NotImplementedError

    def poll_system_error(self) -> str:
        raise NotImplementedError

    def abort_measurement(self) -> bool:
        raise NotImplementedError

    def release_to_local(self) -> str:
        raise NotImplementedError

    def cleanup_release_to_local(self, timeout_ms: int = 1000) -> str:
        raise NotImplementedError


def create_instrument_backend(
    config: InstrumentConfig,
    *,
    simulate: bool,
    measurement_type: str,
    resource_manager_factory: Callable[[], object] | None = None,
) -> InstrumentBackend:
    if simulate:
        return SimulatedVisaInstrument(config, measurement_type=measurement_type)
    return VisaInstrument(config, resource_manager_factory=resource_manager_factory)
