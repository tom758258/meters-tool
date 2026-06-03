from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from .instrument import VisaInstrument
from .measurement import MeasurementPlugin
from .models import AcquisitionConfig, TriggerEvent
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
        self._stats = AcquisitionStats()

    @property
    def stats(self) -> AcquisitionStats:
        return self._stats

    def _emit(self, text: str) -> None:
        if self._status_cb:
            self._status_cb(text)

    def run(
        self,
        enable_hardware_trigger: bool = False,
        hardware_trigger_slope: str = "NEG",
    ) -> None:
        self._running = True
        self._measurement.configure(self._instrument, self._config)
        hw = None
        if enable_hardware_trigger:
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
        try:
            while self._running:
                wait_s = self._config.trigger_timeout_ms / 1000.0
                if hw is not None:
                    wait_s = min(wait_s, 0.2)
                ev = self._router.wait(timeout_s=wait_s)
                if ev is None and hw is not None:
                    try:
                        ev = hw.wait_and_read_triggered(self._config.trigger_timeout_ms)
                    except Exception:
                        self._stats.errors += 1
                        if self._running:
                            self._emit("hardware trigger timeout/error")
                        continue
                if ev is None:
                    self._emit("waiting trigger")
                    continue
                if ev.metadata.get("control") == "stop":
                    self._emit("stop request received")
                    self._instrument.abort_measurement()
                    self.stop()
                    continue
                self._capture(ev)
        finally:
            self._storage.close()
            self._emit("recording stopped")

    def _capture(self, event: TriggerEvent) -> None:
        try:
            sample = self._measurement.read_sample(self._instrument, event)
            self._storage.write(sample)
            self._stats.captured += 1
            self._emit(f"captured={self._stats.captured}")
        except Exception:
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
