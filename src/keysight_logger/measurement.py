from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List

from .instrument import VisaInstrument
from .models import AcquisitionConfig, MeasurementSample, TriggerEvent, TriggerSource


def _vm_comp_slope_command(slope: str) -> str:
    slope_cmd = str(slope).strip().upper()
    if slope_cmd in ("POS", "POSITIVE"):
        return "POS"
    if slope_cmd in ("NEG", "NEGATIVE"):
        return "NEG"
    raise ValueError("vm_comp_slope must be 'pos' or 'neg'")


class MeasurementPlugin(ABC):
    @abstractmethod
    def configure(self, instrument: VisaInstrument, config: AcquisitionConfig) -> None:
        raise NotImplementedError

    @abstractmethod
    def read_sample(self, instrument: VisaInstrument, trigger: TriggerEvent) -> MeasurementSample:
        raise NotImplementedError

    @abstractmethod
    def measurement_type(self) -> str:
        raise NotImplementedError

    def configure_immediate_custom(
        self,
        instrument: VisaInstrument,
        config: AcquisitionConfig,
        trigger_count: int,
        sample_count: int,
    ) -> None:
        raise NotImplementedError

    def configure_software_custom(
        self,
        instrument: VisaInstrument,
        config: AcquisitionConfig,
        trigger_count: int,
        sample_count: int,
    ) -> None:
        raise NotImplementedError

    def configure_external_custom(
        self,
        instrument: VisaInstrument,
        config: AcquisitionConfig,
        trigger_count: int,
        sample_count: int,
        slope: str,
        delay_s: float,
    ) -> None:
        raise NotImplementedError

    def send_bus_trigger(self, instrument: VisaInstrument) -> None:
        raise NotImplementedError

    def start_buffered_capture(self, instrument: VisaInstrument) -> None:
        raise NotImplementedError

    def buffered_points_available(self, instrument: VisaInstrument) -> int:
        raise NotImplementedError

    def read_buffered_samples(
        self,
        instrument: VisaInstrument,
        trigger: TriggerEvent,
        count: int,
        first_sample_index: int,
    ) -> List[MeasurementSample]:
        raise NotImplementedError


@dataclass(frozen=True)
class MeasurementDefinition:
    cli_name: str
    internal_type: str
    unit: str
    range_label: str
    accepts_current_range_alias: bool = False


CURRENT_DC_DEFINITION = MeasurementDefinition(
    cli_name="current-dc",
    internal_type="current_dc",
    unit="A",
    range_label="amps",
    accepts_current_range_alias=True,
)
VOLTAGE_DC_DEFINITION = MeasurementDefinition(
    cli_name="voltage-dc",
    internal_type="voltage_dc",
    unit="V",
    range_label="volts",
)


class ScalarDmmMeasurement(MeasurementPlugin):
    def __init__(self, definition: MeasurementDefinition) -> None:
        self.definition = definition
        self._configured = False

    def measurement_type(self) -> str:
        return self.definition.internal_type

    def unit(self) -> str:
        return self.definition.unit

    def _require_configured(self) -> None:
        if not self._configured:
            raise RuntimeError("Measurement plugin not configured")

    def read_sample(self, instrument: VisaInstrument, trigger: TriggerEvent) -> MeasurementSample:
        self._require_configured()
        # Hardware path is pre-armed by trigger adapter (INIT + external trigger),
        # so fetch completed data instead of re-arming another triggered READ?.
        command = "FETC?" if trigger.source == TriggerSource.HARDWARE else "READ?"
        value = instrument.query_ascii_float(command)
        return MeasurementSample(
            timestamp_utc=datetime.now(timezone.utc),
            measurement_type=self.measurement_type(),
            value=value,
            unit=self.unit(),
            status="ok",
            resource_id=instrument.resource_id,
            trigger_id=trigger.id,
            trigger_source=trigger.source.value,
            trigger_metadata=dict(trigger.metadata),
        )

    def configure_immediate_custom(
        self,
        instrument: VisaInstrument,
        config: AcquisitionConfig,
        trigger_count: int,
        sample_count: int,
    ) -> None:
        self._require_configured()
        if trigger_count <= 0:
            raise ValueError("trigger_count must be > 0")
        if sample_count <= 0:
            raise ValueError("sample_count must be > 0")
        instrument.write("TRIG:SOUR IMM")
        instrument.write(f"TRIG:COUNT {trigger_count}")
        instrument.write(f"SAMP:COUNT {sample_count}")

    def configure_software_custom(
        self,
        instrument: VisaInstrument,
        config: AcquisitionConfig,
        trigger_count: int,
        sample_count: int,
    ) -> None:
        self._require_configured()
        if trigger_count <= 0:
            raise ValueError("trigger_count must be > 0")
        if sample_count <= 0:
            raise ValueError("sample_count must be > 0")
        instrument.write("TRIG:SOUR BUS")
        instrument.write(f"TRIG:COUNT {trigger_count}")
        instrument.write(f"SAMP:COUNT {sample_count}")

    def configure_external_custom(
        self,
        instrument: VisaInstrument,
        config: AcquisitionConfig,
        trigger_count: int,
        sample_count: int,
        slope: str,
        delay_s: float,
    ) -> None:
        self._require_configured()
        if trigger_count <= 0:
            raise ValueError("trigger_count must be > 0")
        if sample_count <= 0:
            raise ValueError("sample_count must be > 0")
        slope_cmd = "POS" if str(slope).upper() == "POS" else "NEG"
        instrument.write("TRIG:SOUR EXT")
        instrument.write(f"TRIG:SLOP {slope_cmd}")
        instrument.write(f"TRIG:COUNT {trigger_count}")
        instrument.write(f"SAMP:COUNT {sample_count}")
        instrument.write(f"TRIG:DEL {max(0.0, float(delay_s))}")

    def send_bus_trigger(self, instrument: VisaInstrument) -> None:
        self._require_configured()
        instrument.write("*TRG")

    def start_buffered_capture(self, instrument: VisaInstrument) -> None:
        self._require_configured()
        instrument.write("INIT")

    def buffered_points_available(self, instrument: VisaInstrument) -> int:
        raw = instrument.query("DATA:POINts?")
        try:
            return max(0, int(float(raw)))
        except ValueError as exc:
            raise RuntimeError(f"Failed to parse DATA:POINts? response from '{raw}'") from exc

    def read_buffered_samples(
        self,
        instrument: VisaInstrument,
        trigger: TriggerEvent,
        count: int,
        first_sample_index: int,
    ) -> List[MeasurementSample]:
        self._require_configured()
        if count <= 0:
            return []
        values = _parse_ascii_floats(instrument.query(f"DATA:REMove? {count}"))
        if len(values) != count:
            raise RuntimeError(f"Expected {count} buffered readings, got {len(values)}")
        fetch_time_utc = datetime.now(timezone.utc)
        samples = []
        for offset, value in enumerate(values):
            metadata = dict(trigger.metadata)
            metadata.update(
                {
                    "buffered": "true",
                    "buffer_index": str(first_sample_index + offset),
                    "buffer_batch_size": str(count),
                    "fetch_time_utc": fetch_time_utc.isoformat(),
                    "time_basis": "pc_data_remove_time_not_instrument_sample_time",
                }
            )
            samples.append(
                MeasurementSample(
                    timestamp_utc=fetch_time_utc,
                    measurement_type=self.measurement_type(),
                    value=value,
                    unit=self.unit(),
                    status="ok",
                    resource_id=instrument.resource_id,
                    trigger_id=trigger.id,
                    trigger_source=trigger.source.value,
                    trigger_metadata=metadata,
                )
            )
        return samples


class CurrentDcMeasurement(ScalarDmmMeasurement):
    def __init__(self) -> None:
        super().__init__(CURRENT_DC_DEFINITION)

    def configure(self, instrument: VisaInstrument, config: AcquisitionConfig) -> None:
        manual_range = config.measurement_range
        if manual_range is None:
            manual_range = config.current_range
        instrument.write("CONF:CURR:DC AUTO")
        if config.auto_range:
            instrument.write("CURR:DC:RANG:AUTO ON")
        elif manual_range is not None:
            instrument.write(f"CURR:DC:RANG {manual_range}")
        instrument.write(f"CURR:DC:NPLC {config.nplc}")
        instrument.write(f"ZERO:AUTO {'ON' if config.auto_zero else 'OFF'}")
        if config.vm_comp_slope is not None:
            slope_cmd = _vm_comp_slope_command(config.vm_comp_slope)
            instrument.write(f"OUTP:TRIG:SLOP {slope_cmd}")
        self._configured = True


class VoltageDcMeasurement(ScalarDmmMeasurement):
    def __init__(self) -> None:
        super().__init__(VOLTAGE_DC_DEFINITION)

    def configure(self, instrument: VisaInstrument, config: AcquisitionConfig) -> None:
        instrument.write("CONF:VOLT:DC AUTO")
        if config.auto_range:
            instrument.write("VOLT:DC:RANG:AUTO ON")
        elif config.measurement_range is not None:
            instrument.write(f"VOLT:DC:RANG {config.measurement_range}")
        instrument.write(f"VOLT:DC:NPLC {config.nplc}")
        instrument.write(f"VOLT:DC:ZERO:AUTO {'ON' if config.auto_zero else 'OFF'}")
        if config.vm_comp_slope is not None:
            slope_cmd = _vm_comp_slope_command(config.vm_comp_slope)
            instrument.write(f"OUTP:TRIG:SLOP {slope_cmd}")
        self._configured = True


CurrentMeasurement = CurrentDcMeasurement

_MEASUREMENT_DEFINITIONS = {
    CURRENT_DC_DEFINITION.internal_type: CURRENT_DC_DEFINITION,
    VOLTAGE_DC_DEFINITION.internal_type: VOLTAGE_DC_DEFINITION,
}
_MEASUREMENT_PLUGIN_TYPES: dict[str, type[MeasurementPlugin]] = {
    CURRENT_DC_DEFINITION.internal_type: CurrentDcMeasurement,
    VOLTAGE_DC_DEFINITION.internal_type: VoltageDcMeasurement,
}


def normalize_measurement_type(value: str) -> str:
    return str(value).strip().lower().replace("-", "_")


def format_measurement_type(value: str) -> str:
    normalized = normalize_measurement_type(value)
    definition = _MEASUREMENT_DEFINITIONS.get(normalized)
    if definition is not None:
        return definition.cli_name
    return normalized.replace("_", "-")


def get_measurement_definition(measurement_type: str) -> MeasurementDefinition:
    normalized = normalize_measurement_type(measurement_type)
    try:
        return _MEASUREMENT_DEFINITIONS[normalized]
    except KeyError as exc:
        raise ValueError(f"Unsupported measurement type: {measurement_type}") from exc


def registered_measurement_types() -> tuple[str, ...]:
    return tuple(_MEASUREMENT_DEFINITIONS)


def create_measurement_plugin(measurement_type: str) -> MeasurementPlugin:
    normalized = normalize_measurement_type(measurement_type)
    try:
        plugin_type = _MEASUREMENT_PLUGIN_TYPES[normalized]
    except KeyError as exc:
        raise ValueError(f"Unsupported measurement type: {measurement_type}") from exc
    return plugin_type()


def _parse_ascii_floats(raw: str) -> list[float]:
    text = str(raw).strip()
    if not text:
        return []
    return [float(part.strip()) for part in text.replace("\n", ",").split(",") if part.strip()]
