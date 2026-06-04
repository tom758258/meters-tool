from __future__ import annotations

from dataclasses import dataclass
import math
import threading
import time
from typing import Callable, Optional

from .instrument import VisaInstrument
from .measurement import MeasurementPlugin
from .models import (
    AcquisitionConfig,
    InstrumentProfile,
    MeasurementSample,
    TriggerEvent,
    TriggerSource,
    get_default_instrument_profile,
)
from .storage import CsvWriter
from .trigger import HardwareTriggerAdapter, TriggerRouter


@dataclass
class AcquisitionStats:
    captured: int = 0
    errors: int = 0


def _format_csv_permission_error(exc: PermissionError) -> str:
    filename = getattr(exc, "filename", None)
    target = str(filename) if filename else "CSV output file"
    return (
        f"cannot open CSV output file: {target}\n"
        "reason: permission denied; the file may be open in Excel or another program\n"
        "action: close the file or choose a different --csv path"
    )


def _format_status_value(sample: MeasurementSample) -> str:
    value = float(sample.value)
    unit = sample.unit
    scaled_value = value
    scaled_unit = unit
    abs_value = abs(value)

    if math.isfinite(value):
        if unit == "A":
            if 0 < abs_value < 1e-3:
                scaled_value = value * 1_000_000
                scaled_unit = "uA"
            elif 0 < abs_value < 1:
                scaled_value = value * 1_000
                scaled_unit = "mA"
        elif unit == "V":
            if 0 < abs_value < 1e-3:
                scaled_value = value * 1_000_000
                scaled_unit = "uV"
            elif 0 < abs_value < 1:
                scaled_value = value * 1_000
                scaled_unit = "mV"
        elif unit == "Ohm":
            if abs_value >= 1_000_000:
                scaled_value = value / 1_000_000
                scaled_unit = "MOhm"
            elif abs_value >= 1_000:
                scaled_value = value / 1_000
                scaled_unit = "kOhm"

    return f"value={scaled_value:.6g} {scaled_unit}"


class TriggerAcquisitionEngine:
    def __init__(
        self,
        instrument: VisaInstrument,
        measurement: MeasurementPlugin,
        storage: CsvWriter,
        config: AcquisitionConfig,
        router: TriggerRouter,
        status_cb: Optional[Callable[[str], None]] = None,
        instrument_profile: InstrumentProfile | None = None,
    ):
        self._instrument = instrument
        self._measurement = measurement
        self._storage = storage
        self._config = config
        self._router = router
        self._status_cb = status_cb
        self._instrument_profile = instrument_profile or get_default_instrument_profile()
        self._running = False
        self._stop_event = threading.Event()
        self._stats = AcquisitionStats()
        self._fatal_error: Optional[str] = None

    @property
    def stats(self) -> AcquisitionStats:
        return self._stats

    @property
    def fatal_error(self) -> Optional[str]:
        return self._fatal_error

    def _emit(self, text: str) -> None:
        if self._status_cb:
            self._status_cb(text)

    def _emit_capture_status(self, sample: MeasurementSample) -> None:
        self._emit(f"captured={self._stats.captured} {_format_status_value(sample)}")

    def _record_capture_failure(self, status_prefix: str, exc: Exception) -> None:
        self._stats.errors += 1
        err_text = "unknown"
        if hasattr(self._instrument, "poll_system_error"):
            try:
                err_text = self._instrument.poll_system_error()
            except Exception:
                err_text = "unknown"
        self._fatal_error = (
            f"{status_prefix} failure: {type(exc).__name__}: {exc}; "
            f"scpi_error={err_text}"
        )
        self._emit(f"{status_prefix} error count={self._stats.errors} scpi_error={err_text}")
        self.stop()

    def run(
        self,
        trigger_mode: str = "software",
        enable_hardware_trigger: bool = False,
        hardware_trigger_slope: str = "NEG",
    ) -> None:
        self._running = True
        self._stop_event.clear()
        self._fatal_error = None
        mode = self._resolve_trigger_mode(trigger_mode, enable_hardware_trigger)
        timer_interval_s = self._config.timer_interval_s
        timer_active = timer_interval_s is not None
        if mode in ("immediate-custom", "software-custom", "external-custom"):
            capabilities = self._instrument_profile
            if not capabilities.supports_buffered_reading_memory:
                raise ValueError(f"{capabilities.model} does not support buffered reading memory")
            if mode == "software-custom" and not capabilities.supports_bus_trigger:
                raise ValueError(f"{capabilities.model} does not support bus trigger")
            if mode == "external-custom" and not capabilities.supports_external_trigger:
                raise ValueError(f"{capabilities.model} does not support external trigger")
            if self._config.trigger_count is None:
                raise ValueError(f"{mode} mode requires trigger_count")
            if self._config.sample_count is None:
                raise ValueError(f"{mode} mode requires sample_count")
            memory_limit = capabilities.reading_memory_limit
            expected_readings = self._config.trigger_count * self._config.sample_count
            if expected_readings > memory_limit and not self._config.allow_buffer_overflow_risk:
                raise ValueError(
                    f"{mode} expected readings exceed "
                    f"{memory_limit} on the {capabilities.model}"
                )
        if timer_active:
            if timer_interval_s <= 0:
                raise ValueError("timer_interval_s must be > 0")
            if mode != "software":
                raise ValueError("timer_interval_s requires software trigger mode")
        self._measurement.configure(self._instrument, self._config)
        hw = None
        if mode == "external":
            hw = HardwareTriggerAdapter(self._instrument)
            hw.configure_external_trigger(
                slope=hardware_trigger_slope,
                delay_s=self._config.hw_trigger_delay_s,
            )
            self._emit(
                "hardware trigger configured "
                f"slope={hardware_trigger_slope.upper()} delay_s={self._config.hw_trigger_delay_s}"
            )
        try:
            self._storage.open()
        except PermissionError as exc:
            self._stats.errors += 1
            self._fatal_error = _format_csv_permission_error(exc)
            self._running = False
            return
        self._emit("recording started")
        if timer_active:
            self._emit(f"software timer enabled interval_s={timer_interval_s}")
        try:
            if mode == "immediate-custom":
                self._capture_immediate_custom(
                    trigger_count=self._config.trigger_count,
                    sample_count=self._config.sample_count,
                )
                return
            if mode == "software-custom":
                self._capture_software_custom(
                    trigger_count=self._config.trigger_count,
                    sample_count=self._config.sample_count,
                )
                return
            if mode == "external-custom":
                self._capture_external_custom(
                    trigger_count=self._config.trigger_count,
                    sample_count=self._config.sample_count,
                    slope=hardware_trigger_slope,
                )
                return
            waiting_trigger_emitted = False
            while self._running and not self._stop_event.is_set():
                wait_s = min(self._config.trigger_timeout_ms / 1000.0, 0.2)
                if timer_active:
                    if not self._drain_timer_control_events():
                        continue
                    ev = TriggerEvent.new(TriggerSource.TIMER)
                elif mode == "immediate":
                    ev = self._router.wait(timeout_s=0)
                    if ev is None:
                        ev = TriggerEvent.new(TriggerSource.IMMEDIATE)
                else:
                    ev = self._router.wait(timeout_s=wait_s)
                if ev is None and hw is not None:
                    try:
                        ev = hw.wait_and_read_triggered(
                            self._config.trigger_timeout_ms,
                            stop_event=self._stop_event,
                        )
                    except TimeoutError:
                        # No external edge within the timeout window; keep waiting.
                        if self._running:
                            hw.recover_from_timeout()
                            self._emit(
                                "hardware trigger wait timed out; re-armed and waiting for next edge"
                            )
                        continue
                    except Exception:
                        if self._running:
                            self._stats.errors += 1
                            self._emit("hardware trigger timeout/error")
                        continue
                if ev is None:
                    if not waiting_trigger_emitted:
                        self._emit("waiting trigger")
                        waiting_trigger_emitted = True
                    continue
                waiting_trigger_emitted = False
                if self._handle_control_event(ev):
                    continue
                if hw is not None and ev.source == TriggerSource.SOFTWARE:
                    self._emit("software trigger ignored while hardware trigger is enabled")
                    continue
                if mode == "immediate" and ev.source == TriggerSource.SOFTWARE:
                    self._emit("software trigger ignored while immediate mode is enabled")
                    continue
                self._capture(ev)
                if self._config.max_samples is not None and self._stats.captured >= self._config.max_samples:
                    self._emit(f"max samples reached: {self._config.max_samples}")
                    self.stop()
                if timer_active and self._running and not self._stop_event.is_set():
                    self._wait_timer_interval(timer_interval_s)
        finally:
            if self._stop_event.is_set():
                self._abort_measurement()
            self._storage.close()
            self._emit("recording stopped")

    def _new_custom_event(
        self,
        source: TriggerSource,
        trigger_count: int,
        sample_count: int,
    ) -> TriggerEvent:
        expected_readings = trigger_count * sample_count
        return TriggerEvent.new(
            source,
            {
                "trigger_count": str(trigger_count),
                "sample_count": str(sample_count),
                "expected_readings": str(expected_readings),
                "time_basis": "pc_data_remove_time_not_instrument_sample_time",
            },
        )

    def _capture_immediate_custom(self, trigger_count: int, sample_count: int) -> None:
        expected_readings = trigger_count * sample_count
        event = self._new_custom_event(
            TriggerSource.IMMEDIATE_CUSTOM,
            trigger_count,
            sample_count,
        )
        self._measurement.configure_immediate_custom(
            self._instrument,
            self._config,
            trigger_count,
            sample_count,
        )
        self._emit(
            "immediate custom capture configured "
            f"trigger_count={trigger_count} sample_count={sample_count} "
            f"expected_readings={expected_readings}"
        )
        self._measurement.start_buffered_capture(self._instrument)
        self._emit("immediate custom capture started")
        self._drain_buffered_custom_capture(event, expected_readings)

    def _capture_software_custom(self, trigger_count: int, sample_count: int) -> None:
        expected_readings = trigger_count * sample_count
        event = self._new_custom_event(
            TriggerSource.SOFTWARE_CUSTOM,
            trigger_count,
            sample_count,
        )
        self._measurement.configure_software_custom(
            self._instrument,
            self._config,
            trigger_count,
            sample_count,
        )
        self._emit(
            "software custom capture configured "
            f"trigger_count={trigger_count} sample_count={sample_count} "
            f"expected_readings={expected_readings}"
        )
        self._measurement.start_buffered_capture(self._instrument)
        self._emit("software custom capture armed")

        triggers_sent = 0
        waiting_trigger_emitted = False
        while self._running and not self._stop_event.is_set() and self._stats.captured < expected_readings:
            try:
                available = self._measurement.buffered_points_available(self._instrument)
                observed_readings = self._stats.captured + available
                remaining = expected_readings - self._stats.captured
                read_count = min(available, remaining)
                if self._config.buffer_drain_size is not None:
                    read_count = min(read_count, self._config.buffer_drain_size)
                if read_count > 0:
                    samples = self._measurement.read_buffered_samples(
                        self._instrument,
                        event,
                        read_count,
                        first_sample_index=self._stats.captured,
                    )
                    for sample in samples:
                        self._storage.write(sample)
                        self._stats.captured += 1
                    self._emit_capture_status(samples[-1])
                    continue

                ready_for_next_trigger = observed_readings >= triggers_sent * sample_count
                if triggers_sent < trigger_count and ready_for_next_trigger:
                    ev = self._router.wait(timeout_s=min(self._config.trigger_timeout_ms / 1000.0, 0.2))
                    if ev is None:
                        if not waiting_trigger_emitted:
                            self._emit("waiting software custom trigger")
                            waiting_trigger_emitted = True
                        continue
                    waiting_trigger_emitted = False
                    if self._handle_control_event(ev):
                        continue
                    if ev.source != TriggerSource.SOFTWARE:
                        continue
                    self._measurement.send_bus_trigger(self._instrument)
                    triggers_sent += 1
                    self._emit(f"software custom trigger sent={triggers_sent}/{trigger_count}")
                    continue

                self._stop_event.wait(0.05)
            except Exception as exc:
                if not self._running:
                    return
                self._record_capture_failure("buffered capture", exc)
                return
        if self._stats.captured >= expected_readings:
            self._emit(f"expected readings reached: {expected_readings}")
            self.stop()

    def _capture_external_custom(self, trigger_count: int, sample_count: int, slope: str) -> None:
        expected_readings = trigger_count * sample_count
        event = self._new_custom_event(
            TriggerSource.EXTERNAL_CUSTOM,
            trigger_count,
            sample_count,
        )
        self._measurement.configure_external_custom(
            self._instrument,
            self._config,
            trigger_count,
            sample_count,
            slope=slope,
            delay_s=self._config.hw_trigger_delay_s,
        )
        self._emit(
            "external custom capture configured "
            f"trigger_count={trigger_count} sample_count={sample_count} "
            f"expected_readings={expected_readings} slope={str(slope).upper()} "
            f"delay_s={self._config.hw_trigger_delay_s}"
        )
        self._measurement.start_buffered_capture(self._instrument)
        self._emit("external custom capture armed")
        self._drain_buffered_custom_capture(
            event,
            expected_readings,
            poll_control_events=True,
            ignored_software_trigger_status="software trigger ignored while external custom is enabled",
        )

    def _drain_buffered_custom_capture(
        self,
        event: TriggerEvent,
        expected_readings: int,
        poll_control_events: bool = False,
        ignored_software_trigger_status: Optional[str] = None,
    ) -> None:
        while self._running and not self._stop_event.is_set() and self._stats.captured < expected_readings:
            try:
                available = self._measurement.buffered_points_available(self._instrument)
                remaining = expected_readings - self._stats.captured
                read_count = min(available, remaining)
                if self._config.buffer_drain_size is not None:
                    read_count = min(read_count, self._config.buffer_drain_size)
                if read_count <= 0:
                    if poll_control_events and not self._drain_custom_control_events(
                        ignored_software_trigger_status
                    ):
                        return
                    self._stop_event.wait(0.05)
                    continue
                samples = self._measurement.read_buffered_samples(
                    self._instrument,
                    event,
                    read_count,
                    first_sample_index=self._stats.captured,
                )
                for sample in samples:
                    self._storage.write(sample)
                    self._stats.captured += 1
                self._emit_capture_status(samples[-1])
            except Exception as exc:
                if not self._running:
                    return
                self._record_capture_failure("buffered capture", exc)
                return
            if poll_control_events and not self._drain_custom_control_events(ignored_software_trigger_status):
                return
        if self._stats.captured >= expected_readings:
            self._emit(f"expected readings reached: {expected_readings}")
            self.stop()

    def _capture(self, event: TriggerEvent) -> None:
        try:
            sample = self._measurement.read_sample(self._instrument, event)
            self._storage.write(sample)
            self._stats.captured += 1
            self._emit_capture_status(sample)
        except Exception as exc:
            if not self._running:
                return
            self._record_capture_failure("capture", exc)

    def stop(self) -> None:
        self._running = False
        self._stop_event.set()

    def _handle_control_event(self, event: TriggerEvent) -> bool:
        if event.metadata.get("control") != "stop":
            return False
        self._emit("stop request received")
        self._abort_measurement()
        self.stop()
        return True

    def _drain_timer_control_events(self) -> bool:
        while self._running and not self._stop_event.is_set():
            event = self._router.wait(timeout_s=0)
            if event is None:
                return True
            if self._handle_control_event(event):
                return False
            if event.source == TriggerSource.SOFTWARE:
                self._emit("software trigger ignored while software timer is enabled")
        return False

    def _drain_custom_control_events(self, ignored_software_trigger_status: Optional[str]) -> bool:
        while self._running and not self._stop_event.is_set():
            event = self._router.wait(timeout_s=0)
            if event is None:
                return True
            if self._handle_control_event(event):
                return False
            if event.source == TriggerSource.SOFTWARE and ignored_software_trigger_status:
                self._emit(ignored_software_trigger_status)
        return False

    def _wait_timer_interval(self, interval_s: float) -> None:
        deadline = time.monotonic() + interval_s
        while self._running and not self._stop_event.is_set():
            remaining_s = deadline - time.monotonic()
            if remaining_s <= 0:
                return
            event = self._router.wait(timeout_s=min(remaining_s, 0.2))
            if event is None:
                continue
            if self._handle_control_event(event):
                return
            if event.source == TriggerSource.SOFTWARE:
                self._emit("software trigger ignored while software timer is enabled")

    def _resolve_trigger_mode(self, trigger_mode: str, enable_hardware_trigger: bool) -> str:
        if enable_hardware_trigger:
            return "external"
        mode = str(trigger_mode).strip().lower()
        if mode not in (
            "software",
            "external",
            "immediate",
            "immediate-custom",
            "software-custom",
            "external-custom",
        ):
            raise ValueError(
                "trigger_mode must be software, external, immediate, immediate-custom, software-custom, or external-custom"
            )
        return mode

    def _abort_measurement(self) -> None:
        # Keep VISA I/O on the worker side of the shutdown path.
        try:
            self._instrument.abort_measurement()
        except Exception:
            pass
