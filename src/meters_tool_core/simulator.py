from __future__ import annotations

from dataclasses import dataclass
from collections import deque
from .models import InstrumentConfig, KEYSIGHT_34460A_PROFILE, KEYSIGHT_34461A_PROFILE


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
    trigger_count_infinite: bool = False
    triggers_received: int = 0
    samples_read: int = 0
    sample_count: int = 1
    source: str = "READ"
    overflow_event: bool = False
    overflow_condition: bool = False
    last_signal_voltage_v: float = 2.46
    last_reference_voltage_v: float = 2.0
    standard_event_complete: bool = False
    sequence_complete: bool = False
    operation_complete_requested: bool = False


class SimulatedVisaInstrument:
    def __init__(
        self,
        config: InstrumentConfig,
        measurement_type: str = "current_dc",
        *,
        overflow_after_samples: int | None = None,
    ):
        self._config = config
        self._closed = False
        self._writes: deque[str] = deque(maxlen=1000)
        self._timeout_ms = config.timeout_ms
        self._overflow_after_samples = overflow_after_samples
        self._state = SimulatedMeasurementState(measurement_type=measurement_type)
        self._resource_id = config.resource_string
        self._profile = (
            KEYSIGHT_34460A_PROFILE
            if config.expected_model == "34460A" or config.resource_string == "SIM::34460A"
            else KEYSIGHT_34461A_PROFILE
        )

    def connect(self) -> None:
        return None

    def _is_ratio_measurement(self) -> bool:
        return self._state.measurement_type == "voltage_dc_ratio"

    def _record_ratio_secondary(self, ratio: float) -> None:
        reference_voltage_v = 2.0
        self._state.last_signal_voltage_v = ratio * reference_voltage_v
        self._state.last_reference_voltage_v = reference_voltage_v

    def _record_overflow(self) -> None:
        self._state.overflow_event = True
        self._state.overflow_condition = True

    def _reset_overflow(self) -> None:
        self._state.overflow_event = False
        self._state.overflow_condition = False

    def _finite_point_limit(self) -> int:
        return self._state.trigger_count * self._state.sample_count

    def _add_points(self, count: int) -> None:
        available = self._state.points_available + count
        if available > self._profile.reading_memory_limit:
            self._record_overflow()
        self._state.points_available = min(available, self._profile.reading_memory_limit)

    def _operation_complete(self) -> bool:
        complete = self._state.standard_event_complete
        self._state.standard_event_complete = False
        return complete

    def _complete_sequence(self) -> None:
        self._state.sequence_complete = True
        if self._state.operation_complete_requested:
            self._state.standard_event_complete = True
            self._state.operation_complete_requested = False

    def write(self, command: str) -> None:
        self._writes.append(command)
        normalized = command.strip().upper()
        if normalized == "*CLS":
            self._state.standard_event_complete = False
            return
        if normalized == "*OPC":
            if self._state.sequence_complete or not self._state.armed:
                self._state.standard_event_complete = True
            else:
                self._state.operation_complete_requested = True
            return
        if normalized.startswith("CONF:VOLT:DC:RAT"):
            self._state.measurement_type = "voltage_dc_ratio"
            return
        if normalized == "ABOR":
            self._state.armed = False
            self._state.overflow_condition = False
            return
        if normalized == "INIT":
            self._state.armed = True
            self._state.triggers_received = 0
            self._state.samples_read = 0
            self._state.standard_event_complete = False
            self._state.sequence_complete = False
            self._state.operation_complete_requested = False
            self._reset_overflow()
            if self._state.source in {"IMM", "EXT"}:
                if self._state.trigger_count_infinite:
                    self._state.points_available = 0
                else:
                    self._state.points_available = 0
                    self._add_points(self._finite_point_limit())
                    self._complete_sequence()
            return
        if normalized == "*TRG":
            if self._state.trigger_count_infinite:
                self._add_points(self._state.sample_count)
            else:
                if self._state.triggers_received < self._state.trigger_count:
                    self._add_points(self._state.sample_count)
            self._state.triggers_received += 1
            if not self._state.trigger_count_infinite and self._state.triggers_received >= self._state.trigger_count:
                self._complete_sequence()
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
            argument = command.split()[-1]
            if argument.upper() == "INF":
                self._state.trigger_count_infinite = True
                self._state.trigger_count = 0
            else:
                try:
                    self._state.trigger_count = int(float(argument))
                    self._state.trigger_count_infinite = False
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
            return f"Keysight Technologies,{self._profile.model},MYSIMULATED,1.0"
        if normalized == "SYST:ERR?":
            return "0,No error"
        if normalized == "*ESR?":
            return "1" if self._operation_complete() else "0"
        if normalized == "STAT:QUES:EVEN?":
            asserted = self._state.overflow_event
            self._state.overflow_event = False
            return "16384" if asserted else "0"
        if normalized == "STAT:QUES:COND?":
            return "16384" if self._state.overflow_condition else "0"
        if normalized == "STAT:OPER:COND?":
            return "32" if self._state.armed else "0"
        if normalized == "DATA:POINTS?":
            if (
                self._state.source == "IMM"
                and self._state.trigger_count_infinite
                and self._state.armed
                and self._state.points_available == 0
            ):
                self._add_points(self._state.sample_count)
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
            self._state.samples_read += max(0, count)
            if (
                self._overflow_after_samples is not None
                and self._state.samples_read >= self._overflow_after_samples
            ):
                self._record_overflow()
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
        self._state.overflow_condition = False
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
