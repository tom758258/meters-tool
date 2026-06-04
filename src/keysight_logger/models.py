from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional
from uuid import uuid4


class Transport(str, Enum):
    LAN = "LAN"
    USB = "USB"


class TriggerSource(str, Enum):
    EXTERNAL_CUSTOM = "external-custom"
    HARDWARE = "hardware"
    IMMEDIATE = "immediate"
    IMMEDIATE_CUSTOM = "immediate-custom"
    SOFTWARE = "software"
    SOFTWARE_CUSTOM = "software-custom"
    TIMER = "timer"


@dataclass(frozen=True)
class InstrumentConfig:
    resource_string: str
    timeout_ms: int = 5000
    transport: Optional[Transport] = None


@dataclass(frozen=True)
class InstrumentProfile:
    vendor: str
    model: str
    aliases: tuple[str, ...]
    reading_memory_limit: int
    supported_measurement_types: tuple[str, ...]
    supports_buffered_reading_memory: bool
    supports_bus_trigger: bool
    supports_external_trigger: bool
    supports_sample_timer: bool

    def matches_idn(self, idn: str) -> bool:
        parts = [part.strip().upper() for part in str(idn).split(",")]
        if len(parts) >= 2 and parts[1] == self.model.upper():
            return True
        normalized = str(idn).strip().upper()
        return any(
            "," in alias
            and (normalized == alias.upper() or normalized.startswith(f"{alias.upper()},"))
            for alias in self.aliases
        )


InstrumentCapabilities = InstrumentProfile


KEYSIGHT_34461A_PROFILE = InstrumentProfile(
    vendor="Keysight",
    model="34461A",
    aliases=(
        "KEYSIGHT TECHNOLOGIES,34461A",
        "KEYSIGHT,34461A",
        "34461A",
    ),
    reading_memory_limit=10000,
    supported_measurement_types=("current_dc", "voltage_dc", "resistance_2w", "resistance_4w"),
    supports_buffered_reading_memory=True,
    supports_bus_trigger=True,
    supports_external_trigger=True,
    supports_sample_timer=False,
)

INSTRUMENT_PROFILES = (KEYSIGHT_34461A_PROFILE,)
DEFAULT_INSTRUMENT_PROFILE = KEYSIGHT_34461A_PROFILE
KEYSIGHT_34461A_CAPABILITIES = KEYSIGHT_34461A_PROFILE


def get_default_instrument_profile() -> InstrumentProfile:
    return DEFAULT_INSTRUMENT_PROFILE


def find_instrument_profile_by_model(model: str) -> InstrumentProfile:
    normalized = str(model).strip().upper()
    for profile in INSTRUMENT_PROFILES:
        if profile.model.upper() == normalized or any(
            alias.upper() == normalized for alias in profile.aliases
        ):
            return profile
    raise ValueError(f"Unsupported instrument model: {model}")


def find_instrument_profile_by_idn(idn: str) -> InstrumentProfile:
    for profile in INSTRUMENT_PROFILES:
        if profile.matches_idn(idn):
            return profile
    raise ValueError(f"Unsupported instrument IDN: {idn}")


@dataclass(frozen=True)
class AcquisitionConfig:
    measurement_type: str = "current_dc"
    trigger_timeout_ms: int = 10000
    max_samples: Optional[int] = None
    trigger_count: Optional[int] = None
    sample_count: Optional[int] = None
    timer_interval_s: Optional[float] = None
    buffer_drain_size: Optional[int] = None
    allow_buffer_overflow_risk: bool = False
    nplc: float = 1.0
    auto_zero: bool = True
    auto_range: bool = True
    measurement_range: Optional[float] = None
    current_range: Optional[float] = None
    hw_trigger_delay_s: float = 0.0
    vm_comp_slope: Optional[str] = None


@dataclass(frozen=True)
class TriggerEvent:
    id: str
    source: TriggerSource
    event_time_utc: datetime
    metadata: Dict[str, str] = field(default_factory=dict)

    @staticmethod
    def new(source: TriggerSource, metadata: Optional[Dict[str, str]] = None) -> "TriggerEvent":
        return TriggerEvent(
            id=str(uuid4()),
            source=source,
            event_time_utc=datetime.now(timezone.utc),
            metadata=metadata or {},
        )


@dataclass(frozen=True)
class MeasurementSample:
    timestamp_utc: datetime
    measurement_type: str
    value: float
    unit: str
    status: str
    resource_id: str
    trigger_id: str
    trigger_source: str
    trigger_metadata: Dict[str, str] = field(default_factory=dict)
