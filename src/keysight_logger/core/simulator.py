from __future__ import annotations

from dataclasses import dataclass
from .models import InstrumentConfig


def _format_ascii_float(value: float) -> str:
    text = f"{float(value):g}"
    return text


@dataclass
class SimulatedMeasurementState:
    measurement_type: str = "current_dc"
    unit: str = "A"
    value_seed: float = 1.23
    points_available: int = 0
    armed: bool = False
    trigger_count: int = 1
    sample_count: int = 1
    source: str = "READ"
    last_signal_voltage_v: float = 2.46
    last_reference_voltage_v: float = 2.0


class SimulatedVisaInstrument:
    def __init__(self, config: InstrumentConfig, measurement_type: str = "current_dc"):
        self._config = config
        self._closed = False
        self._writes: list[str] = []
        self._timeout_ms = config.timeout_ms
        self._state = SimulatedMeasurementState(measurement_type=measurement_type)
        self._resource_id = config.resource_string

    def connect(self) -> None:
        return None

    def _is_ratio_measurement(self) -> bool:
        return self._state.measurement_type == "voltage_dc_ratio"

    def _record_ratio_secondary(self, ratio: float) -> None:
        reference_voltage_v = 2.0
        self._state.last_signal_voltage_v = ratio * reference_voltage_v
        self._state.last_reference_voltage_v = reference_voltage_v

    def write(self, command: str) -> None:
        self._writes.append(command)
        normalized = command.strip().upper()
        if normalized == "*CLS":
            return
        if normalized.startswith("CONF:VOLT:DC:RAT"):
            self._state.measurement_type = "voltage_dc_ratio"
            return
        if normalized == "ABOR":
            self._state.armed = False
            return
        if normalized == "INIT":
            self._state.armed = True
            if self._state.source in {"IMM", "EXT"}:
                self._state.points_available = self._state.trigger_count * self._state.sample_count
            return
        if normalized == "*TRG":
            self._state.points_available = min(
                self._state.trigger_count * self._state.sample_count,
                self._state.points_available + self._state.sample_count,
            )
            return
        if normalized.startswith("TRIG:SOUR"):
            if "IMM" in normalized:
                self._state.source = "IMM"
            elif "BUS" in normalized:
                self._state.source = "BUS"
            elif "EXT" in normalized:
                self._state.source = "EXT"
            return
        if normalized.startswith("TRIG:COUNT"):
            try:
                self._state.trigger_count = int(float(command.split()[-1]))
            except Exception:
                pass
            return
        if normalized.startswith("SAMP:COUNT"):
            try:
                self._state.sample_count = int(float(command.split()[-1]))
            except Exception:
                pass
            return
        if normalized.startswith("DATA:REMOVE?"):
            return

    def query(self, command: str) -> str:
        normalized = command.strip().upper()
        self._writes.append(f"query:{command}")
        if normalized == "*IDN?":
            return "Keysight Technologies,34461A,MYSIMULATED,1.0"
        if normalized == "SYST:ERR?":
            return "0,No error"
        if normalized == "DATA:POINTS?":
            return str(max(0, self._state.points_available))
        if normalized == "DATA2?":
            return ",".join(
                (
                    _format_ascii_float(self._state.last_signal_voltage_v),
                    _format_ascii_float(self._state.last_reference_voltage_v),
                )
            )
        if normalized.startswith("DATA:REMOVE?"):
            try:
                count = int(float(command.split()[-1]))
            except Exception:
                count = 0
            values = []
            for index in range(max(0, count)):
                value = self._state.value_seed + index
                if self._is_ratio_measurement():
                    self._record_ratio_secondary(value)
                values.append(_format_ascii_float(value))
            self._state.points_available = max(0, self._state.points_available - count)
            self._state.value_seed += max(0, count)
            return ",".join(values)
        if normalized in {"READ?", "FETC?"}:
            value = self._state.value_seed
            if self._is_ratio_measurement():
                self._record_ratio_secondary(value)
            self._state.value_seed += 1.0
            return _format_ascii_float(value)
        return "1.23"

    def query_ascii_float(self, command: str) -> float:
        return float(self.query(command))

    def read_status_byte(self) -> int:
        if self._state.armed:
            return 32
        return 0

    def set_timeout_ms(self, timeout_ms: int) -> None:
        self._timeout_ms = timeout_ms

    def clear(self) -> None:
        return None

    def control_ren(self, _mode: int) -> None:
        return None

    def abort_measurement(self) -> bool:
        self._state.armed = False
        return True

    def poll_system_error(self) -> str:
        return "0,No error"

    def release_to_local(self) -> str:
        return "simulated_release_to_local"

    def cleanup_release_to_local(self, timeout_ms: int = 1000) -> str:  # noqa: ARG002
        return "simulated_cleanup_release_to_local"

    def close(self) -> None:
        self._closed = True

    @property
    def resource_id(self) -> str:
        return self._resource_id
