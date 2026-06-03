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
    HARDWARE = "hardware"
    IMMEDIATE = "immediate"
    IMMEDIATE_BUFFERED = "immediate-buffered"
    SOFTWARE = "software"
    TIMER = "timer"


MAX_34461A_BUFFERED_READINGS = 10000


@dataclass(frozen=True)
class InstrumentConfig:
    resource_string: str
    timeout_ms: int = 5000
    transport: Optional[Transport] = None


@dataclass(frozen=True)
class AcquisitionConfig:
    trigger_timeout_ms: int = 10000
    max_samples: Optional[int] = None
    timer_interval_s: Optional[float] = None
    nplc: float = 1.0
    auto_zero: bool = True
    auto_range: bool = True
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
