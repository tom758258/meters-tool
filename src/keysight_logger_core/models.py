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
    expected_model: Optional[str] = None
    visa_library: Optional[str] = None


@dataclass(frozen=True)
class MeasurementOptions:
    measurement_type: str
    range_options: tuple[tuple[str, float], ...] = ()
    nplc_options: tuple[float, ...] = ()
    ac_bandwidth_hz_options: tuple[float, ...] = ()
    gate_time_s_options: tuple[float, ...] = ()
    freq_period_timeout_options: tuple[str, ...] = ()
    current_terminal_options: tuple[int, ...] = ()
    default_auto_range: bool = True
    default_ac_bandwidth_hz: Optional[float] = None
    default_gate_time_s: Optional[float] = None
    default_freq_period_timeout: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "measurement_type",
            str(self.measurement_type).strip().lower().replace("-", "_"),
        )


@dataclass(frozen=True)
class InstrumentProfile:
    vendor: str
    model: str
    aliases: tuple[str, ...]
    reading_memory_limit: int
    supports_buffered_reading_memory: bool
    supports_bus_trigger: bool
    supports_external_trigger: bool
    supports_sample_timer: bool
    measurement_options: tuple[MeasurementOptions, ...] = ()
    supported_measurement_types: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.measurement_options:
            object.__setattr__(
                self,
                "supported_measurement_types",
                tuple(option.measurement_type for option in self.measurement_options),
            )
        elif self.supported_measurement_types and not self.measurement_options:
            object.__setattr__(
                self,
                "measurement_options",
                tuple(
                    MeasurementOptions(measurement_type=measurement_type)
                    for measurement_type in self.supported_measurement_types
                ),
            )

    def get_measurement_options(self, measurement_type: str) -> MeasurementOptions:
        normalized = str(measurement_type).strip().lower().replace("-", "_")
        for options in self.measurement_options:
            if options.measurement_type == normalized:
                return options
        raise ValueError(f"{self.model} does not support measurement type: {measurement_type}")

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


KEYSIGHT_34461A_CURRENT_RANGES = (
    ("100 uA", 0.0001),
    ("1 mA", 0.001),
    ("10 mA", 0.01),
    ("100 mA", 0.1),
    ("1 A", 1.0),
    ("3 A", 3.0),
    ("10 A (front 10A terminal)", 10.0),
)
KEYSIGHT_34460A_CURRENT_RANGES = (
    ("100 uA", 0.0001),
    ("1 mA", 0.001),
    ("10 mA", 0.01),
    ("100 mA", 0.1),
    ("1 A", 1.0),
    ("3 A", 3.0),
)
KEYSIGHT_34461A_DCV_RANGES = (
    ("100 mV", 0.1),
    ("1 V", 1.0),
    ("10 V", 10.0),
    ("100 V", 100.0),
    ("1000 V", 1000.0),
)
KEYSIGHT_34461A_ACV_RANGES = (
    ("100 mV", 0.1),
    ("1 V", 1.0),
    ("10 V", 10.0),
    ("100 V", 100.0),
    ("750 V", 750.0),
)
KEYSIGHT_34461A_FREQ_PERIOD_VOLTAGE_RANGES = KEYSIGHT_34461A_ACV_RANGES
KEYSIGHT_34461A_RESISTANCE_RANGES = (
    ("100 Ohm", 100.0),
    ("1 kOhm", 1_000.0),
    ("10 kOhm", 10_000.0),
    ("100 kOhm", 100_000.0),
    ("1 MOhm", 1_000_000.0),
    ("10 MOhm", 10_000_000.0),
    ("100 MOhm", 100_000_000.0),
)
KEYSIGHT_34461A_NPLC_OPTIONS = (0.02, 0.2, 1.0, 10.0, 100.0)
KEYSIGHT_34461A_FREQ_PERIOD_GATE_TIME_OPTIONS = (0.01, 0.1, 1.0)
KEYSIGHT_34461A_FREQ_PERIOD_TIMEOUT_OPTIONS = ("auto", "1s")
KEYSIGHT_34461A_FREQ_PERIOD_DEFAULT_AC_BANDWIDTH_HZ = 20.0
KEYSIGHT_34461A_FREQ_PERIOD_DEFAULT_GATE_TIME_S = 0.1
KEYSIGHT_34461A_FREQ_PERIOD_DEFAULT_TIMEOUT = "auto"


KEYSIGHT_34461A_PROFILE = InstrumentProfile(
    vendor="Keysight",
    model="34461A",
    aliases=(
        "KEYSIGHT TECHNOLOGIES,34461A",
        "KEYSIGHT,34461A",
        "34461A",
    ),
    reading_memory_limit=10000,
    measurement_options=(
        MeasurementOptions(
            measurement_type="current_dc",
            range_options=KEYSIGHT_34461A_CURRENT_RANGES,
            nplc_options=KEYSIGHT_34461A_NPLC_OPTIONS,
            current_terminal_options=(3, 10),
        ),
        MeasurementOptions(
            measurement_type="voltage_dc",
            range_options=KEYSIGHT_34461A_DCV_RANGES,
            nplc_options=KEYSIGHT_34461A_NPLC_OPTIONS,
        ),
        MeasurementOptions(
            measurement_type="voltage_dc_ratio",
            range_options=KEYSIGHT_34461A_DCV_RANGES,
            nplc_options=KEYSIGHT_34461A_NPLC_OPTIONS,
        ),
        MeasurementOptions(
            measurement_type="current_ac",
            range_options=KEYSIGHT_34461A_CURRENT_RANGES,
            ac_bandwidth_hz_options=(3.0, 20.0, 200.0),
            current_terminal_options=(3, 10),
        ),
        MeasurementOptions(
            measurement_type="voltage_ac",
            range_options=KEYSIGHT_34461A_ACV_RANGES,
            ac_bandwidth_hz_options=(3.0, 20.0, 200.0),
        ),
        MeasurementOptions(
            measurement_type="frequency",
            range_options=KEYSIGHT_34461A_FREQ_PERIOD_VOLTAGE_RANGES,
            ac_bandwidth_hz_options=(3.0, 20.0, 200.0),
            gate_time_s_options=KEYSIGHT_34461A_FREQ_PERIOD_GATE_TIME_OPTIONS,
            freq_period_timeout_options=KEYSIGHT_34461A_FREQ_PERIOD_TIMEOUT_OPTIONS,
            default_ac_bandwidth_hz=KEYSIGHT_34461A_FREQ_PERIOD_DEFAULT_AC_BANDWIDTH_HZ,
            default_gate_time_s=KEYSIGHT_34461A_FREQ_PERIOD_DEFAULT_GATE_TIME_S,
            default_freq_period_timeout=KEYSIGHT_34461A_FREQ_PERIOD_DEFAULT_TIMEOUT,
        ),
        MeasurementOptions(
            measurement_type="period",
            range_options=KEYSIGHT_34461A_FREQ_PERIOD_VOLTAGE_RANGES,
            ac_bandwidth_hz_options=(3.0, 20.0, 200.0),
            gate_time_s_options=KEYSIGHT_34461A_FREQ_PERIOD_GATE_TIME_OPTIONS,
            default_ac_bandwidth_hz=KEYSIGHT_34461A_FREQ_PERIOD_DEFAULT_AC_BANDWIDTH_HZ,
            default_gate_time_s=KEYSIGHT_34461A_FREQ_PERIOD_DEFAULT_GATE_TIME_S,
        ),
        MeasurementOptions(
            measurement_type="resistance_2w",
            range_options=KEYSIGHT_34461A_RESISTANCE_RANGES,
            nplc_options=KEYSIGHT_34461A_NPLC_OPTIONS,
        ),
        MeasurementOptions(
            measurement_type="resistance_4w",
            range_options=KEYSIGHT_34461A_RESISTANCE_RANGES,
            nplc_options=KEYSIGHT_34461A_NPLC_OPTIONS,
        ),
    ),
    supports_buffered_reading_memory=True,
    supports_bus_trigger=True,
    supports_external_trigger=True,
    supports_sample_timer=False,
)

KEYSIGHT_34460A_PROFILE = InstrumentProfile(
    vendor="Keysight",
    model="34460A",
    aliases=(
        "KEYSIGHT TECHNOLOGIES,34460A",
        "KEYSIGHT,34460A",
        "AGILENT TECHNOLOGIES,34460A",
        "AGILENT,34460A",
        "34460A",
    ),
    reading_memory_limit=1000,
    measurement_options=(
        MeasurementOptions(
            measurement_type="current_dc",
            range_options=KEYSIGHT_34460A_CURRENT_RANGES,
            nplc_options=KEYSIGHT_34461A_NPLC_OPTIONS,
            current_terminal_options=(),
        ),
        MeasurementOptions(
            measurement_type="voltage_dc",
            range_options=KEYSIGHT_34461A_DCV_RANGES,
            nplc_options=KEYSIGHT_34461A_NPLC_OPTIONS,
        ),
        MeasurementOptions(
            measurement_type="voltage_dc_ratio",
            range_options=KEYSIGHT_34461A_DCV_RANGES,
            nplc_options=KEYSIGHT_34461A_NPLC_OPTIONS,
        ),
        MeasurementOptions(
            measurement_type="current_ac",
            range_options=KEYSIGHT_34460A_CURRENT_RANGES,
            ac_bandwidth_hz_options=(3.0, 20.0, 200.0),
            current_terminal_options=(),
        ),
        MeasurementOptions(
            measurement_type="voltage_ac",
            range_options=KEYSIGHT_34461A_ACV_RANGES,
            ac_bandwidth_hz_options=(3.0, 20.0, 200.0),
        ),
        MeasurementOptions(
            measurement_type="frequency",
            range_options=KEYSIGHT_34461A_FREQ_PERIOD_VOLTAGE_RANGES,
            ac_bandwidth_hz_options=(3.0, 20.0, 200.0),
            gate_time_s_options=KEYSIGHT_34461A_FREQ_PERIOD_GATE_TIME_OPTIONS,
            freq_period_timeout_options=KEYSIGHT_34461A_FREQ_PERIOD_TIMEOUT_OPTIONS,
            default_ac_bandwidth_hz=KEYSIGHT_34461A_FREQ_PERIOD_DEFAULT_AC_BANDWIDTH_HZ,
            default_gate_time_s=KEYSIGHT_34461A_FREQ_PERIOD_DEFAULT_GATE_TIME_S,
            default_freq_period_timeout=KEYSIGHT_34461A_FREQ_PERIOD_DEFAULT_TIMEOUT,
        ),
        MeasurementOptions(
            measurement_type="period",
            range_options=KEYSIGHT_34461A_FREQ_PERIOD_VOLTAGE_RANGES,
            ac_bandwidth_hz_options=(3.0, 20.0, 200.0),
            gate_time_s_options=KEYSIGHT_34461A_FREQ_PERIOD_GATE_TIME_OPTIONS,
            default_ac_bandwidth_hz=KEYSIGHT_34461A_FREQ_PERIOD_DEFAULT_AC_BANDWIDTH_HZ,
            default_gate_time_s=KEYSIGHT_34461A_FREQ_PERIOD_DEFAULT_GATE_TIME_S,
        ),
        MeasurementOptions(
            measurement_type="resistance_2w",
            range_options=KEYSIGHT_34461A_RESISTANCE_RANGES,
            nplc_options=KEYSIGHT_34461A_NPLC_OPTIONS,
        ),
        MeasurementOptions(
            measurement_type="resistance_4w",
            range_options=KEYSIGHT_34461A_RESISTANCE_RANGES,
            nplc_options=KEYSIGHT_34461A_NPLC_OPTIONS,
        ),
    ),
    supports_buffered_reading_memory=True,
    supports_bus_trigger=True,
    supports_external_trigger=False,
    supports_sample_timer=False,
)

INSTRUMENT_PROFILES = (KEYSIGHT_34461A_PROFILE, KEYSIGHT_34460A_PROFILE)
DEFAULT_INSTRUMENT_PROFILE = KEYSIGHT_34461A_PROFILE
KEYSIGHT_34461A_CAPABILITIES = KEYSIGHT_34461A_PROFILE
KEYSIGHT_34460A_CAPABILITIES = KEYSIGHT_34460A_PROFILE


def get_default_instrument_profile() -> InstrumentProfile:
    return DEFAULT_INSTRUMENT_PROFILE


def supported_instrument_models() -> tuple[str, ...]:
    return tuple(sorted(profile.model for profile in INSTRUMENT_PROFILES))


def find_instrument_profile_by_model(model: str) -> InstrumentProfile:
    normalized = str(model).strip().upper()
    for profile in INSTRUMENT_PROFILES:
        if profile.model.upper() == normalized or any(
            alias.upper() == normalized for alias in profile.aliases
        ):
            return profile
    supported = ", ".join(supported_instrument_models())
    raise ValueError(f"Unsupported instrument model: {model}. Supported models: {supported}")


def normalize_requested_model(model: str | None) -> str | None:
    if model is None:
        return None
    text = str(model).strip()
    if not text:
        return None
    return find_instrument_profile_by_model(text).model


def resolve_instrument_profile(model: str | None = None) -> InstrumentProfile:
    if model is None:
        return get_default_instrument_profile()
    return find_instrument_profile_by_model(model)


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
    auto_zero: bool | str = True
    auto_range: bool = True
    measurement_range: Optional[float] = None
    current_range: Optional[float] = None
    ac_bandwidth_hz: Optional[float] = None
    gate_time_s: Optional[float] = None
    freq_period_timeout: Optional[str] = None
    current_terminal: Optional[int] = None
    dcv_input_impedance: str = "default"
    hw_trigger_delay_s: float = 0.0
    vm_comp_slope: Optional[str] = None


@dataclass(frozen=True)
class StartRequest:
    resource: str
    instrument_model: Optional[str] = None
    visa_library: Optional[str] = None
    csv: Optional[str] = None
    dry_run: bool = False
    simulate: bool = False
    timeout_ms: int = 5000
    trigger_timeout_ms: int = 10000
    sw_trigger_port: int = 8765
    sw_min_interval_ms: int = 0
    sw_queue_max: int = 0
    trigger_mode: Optional[str] = None
    max_samples: Optional[int] = None
    trigger_count: Optional[int] = None
    sample_count: Optional[int] = None
    timer_interval_s: Optional[float] = None
    buffer_drain_size: Optional[int] = None
    allow_buffer_overflow_risk: bool = False
    hw_trigger_slope: str = "neg"
    hw_trigger_delay_s: float = 0.0
    measurement: str = "current-dc"
    nplc: float = 1.0
    auto_zero: bool | str = True
    auto_range: bool = True
    measurement_range: Optional[float] = None
    current_range: Optional[float] = None
    ac_bandwidth_hz: Optional[float] = None
    gate_time_s: Optional[float] = None
    freq_period_timeout: Optional[str] = None
    current_terminal: Optional[int] = None
    dcv_input_impedance: str = "default"
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
    measurement_metadata: Dict[str, object] = field(default_factory=dict)
