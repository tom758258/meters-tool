from __future__ import annotations

from dataclasses import dataclass
import threading
import time
from typing import Callable, Optional

from .instrument import VisaInstrument
from .measurement import MeasurementPlugin
from .models import MAX_34461A_BUFFERED_READINGS, AcquisitionConfig, TriggerEvent, TriggerSource
from .storage import CsvWriter
from .trigger import HardwareTriggerAdapter, TriggerRouter


@dataclass
class AcquisitionStats:
    captured: int = 0
    errors: int = 0


class TriggerAcquisitionEngine:
    def __init__(
        self,
        instrument: VisaInstrument,
        measurement: MeasurementPlugin,
        storage: CsvWriter,
        config: AcquisitionConfig,
        router: TriggerRouter,
        status_cb: Optional[Callable[[str], None]] = None,
    ):
        self._instrument = instrument
        self._measurement = measurement
        self._storage = storage
        self._config = config
        self._router = router
        self._status_cb = status_cb
        self._running = False
        self._stop_event = threading.Event()
        self._stats = AcquisitionStats()

    @property
    def stats(self) -> AcquisitionStats:
        return self._stats

    def _emit(self, text: str) -> None:
        if self._status_cb:
            self._status_cb(text)

    def run(
        self,
        trigger_mode: str = "software",
        enable_hardware_trigger: bool = False,
        hardware_trigger_slope: str = "NEG",
    ) -> None:
        self._running = True
        self._stop_event.clear()
        mode = self._resolve_trigger_mode(trigger_mode, enable_hardware_trigger)
        timer_interval_s = self._config.timer_interval_s
        timer_active = timer_interval_s is not None
        if mode == "immediate-buffered":
            if self._config.max_samples is None:
                raise ValueError("immediate-buffered mode requires max_samples")
            if self._config.max_samples > MAX_34461A_BUFFERED_READINGS:
                raise ValueError(
                    "immediate-buffered mode supports up to "
                    f"{MAX_34461A_BUFFERED_READINGS} samples on the 34461A"
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
        self._storage.open()
        self._emit("recording started")
        if timer_active:
            self._emit(f"software timer enabled interval_s={timer_interval_s}")
        try:
            if mode == "immediate-buffered":
                self._capture_immediate_buffered(self._config.max_samples)
                return
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
                    self._emit("waiting trigger")
                    continue
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

    def _capture_immediate_buffered(self, sample_count: int) -> None:
        event = TriggerEvent.new(
            TriggerSource.IMMEDIATE_BUFFERED,
            {
                "buffer_target_count": str(sample_count),
                "time_basis": "pc_data_remove_time_not_instrument_sample_time",
            },
        )
        self._measurement.configure_immediate_buffered(self._instrument, self._config, sample_count)
        self._emit(f"immediate buffered capture configured samples={sample_count}")
        self._measurement.start_buffered_capture(self._instrument)
        self._emit("immediate buffered capture started")
        while self._running and not self._stop_event.is_set() and self._stats.captured < sample_count:
            try:
                available = self._measurement.buffered_points_available(self._instrument)
                remaining = sample_count - self._stats.captured
                read_count = min(available, remaining)
                if read_count <= 0:
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
                self._emit(f"captured={self._stats.captured}")
            except Exception:
                if not self._running:
                    return
                self._stats.errors += 1
                err_text = "unknown"
                if hasattr(self._instrument, "poll_system_error"):
                    try:
                        err_text = self._instrument.poll_system_error()
                    except Exception:
                        err_text = "unknown"
                self._emit(f"buffered capture error count={self._stats.errors} scpi_error={err_text}")
                self.stop()
                return
        if self._stats.captured >= sample_count:
            self._emit(f"max samples reached: {sample_count}")
            self.stop()

    def _capture(self, event: TriggerEvent) -> None:
        try:
            sample = self._measurement.read_sample(self._instrument, event)
            self._storage.write(sample)
            self._stats.captured += 1
            self._emit(f"captured={self._stats.captured}")
        except Exception:
            if not self._running:
                return
            self._stats.errors += 1
            err_text = "unknown"
            if hasattr(self._instrument, "poll_system_error"):
                try:
                    err_text = self._instrument.poll_system_error()
                except Exception:
                    err_text = "unknown"
            self._emit(f"capture error count={self._stats.errors} scpi_error={err_text}")

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
        if mode not in ("software", "external", "immediate", "immediate-buffered"):
            raise ValueError(
                "trigger_mode must be software, external, immediate, or immediate-buffered"
            )
        return mode

    def _abort_measurement(self) -> None:
        # Keep VISA I/O on the worker side of the shutdown path.
        try:
            self._instrument.abort_measurement()
        except Exception:
            pass
