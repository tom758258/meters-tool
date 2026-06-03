from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone

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


class CurrentMeasurement(MeasurementPlugin):
    def __init__(self) -> None:
        self._configured = False

    def measurement_type(self) -> str:
        return "current_dc"

    def configure(self, instrument: VisaInstrument, config: AcquisitionConfig) -> None:
        instrument.write("CONF:CURR:DC AUTO")
        if config.auto_range:
            instrument.write("CURR:DC:RANG:AUTO ON")
        elif config.current_range is not None:
            instrument.write(f"CURR:DC:RANG {config.current_range}")
        instrument.write(f"CURR:DC:NPLC {config.nplc}")
        instrument.write(f"ZERO:AUTO {'ON' if config.auto_zero else 'OFF'}")
        if config.vm_comp_slope is not None:
            slope_cmd = _vm_comp_slope_command(config.vm_comp_slope)
            instrument.write(f"OUTP:TRIG:SLOP {slope_cmd}")
        self._configured = True

    def read_sample(self, instrument: VisaInstrument, trigger: TriggerEvent) -> MeasurementSample:
        if not self._configured:
            raise RuntimeError("Measurement plugin not configured")
        # Hardware path is pre-armed by trigger adapter (INIT + external trigger),
        # so fetch completed data instead of re-arming another triggered READ?.
        command = "FETC?" if trigger.source == TriggerSource.HARDWARE else "READ?"
        value = instrument.query_ascii_float(command)
        return MeasurementSample(
            timestamp_utc=datetime.now(timezone.utc),
            measurement_type=self.measurement_type(),
            value=value,
            unit="A",
            status="ok",
            resource_id=instrument.resource_id,
            trigger_id=trigger.id,
            trigger_source=trigger.source.value,
            trigger_metadata=dict(trigger.metadata),
        )
