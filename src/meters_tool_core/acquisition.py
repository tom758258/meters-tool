from __future__ import annotations

from dataclasses import dataclass
import math
import threading
import time
from typing import Callable, Optional

from .instrument_backend import InstrumentBackend
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
    trigger_count_infinite: bool = False
    expected_readings: int | None = None
    overflow_monitoring: str = "off"
    overflow_detected: bool | None = None
    stop_reason: str = "unknown"
    final_drain_complete: bool | None = None
    data_integrity: str = "unknown"


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
        instrument: InstrumentBackend,
        measurement: MeasurementPlugin,
        storage: CsvWriter | None,
        config: AcquisitionConfig,
        router: TriggerRouter,
        status_cb: Optional[Callable[[str], None]] = None,
        sample_cb: Optional[Callable[[MeasurementSample, int], None]] = None,
        instrument_profile: InstrumentProfile | None = None,
    ):
        self._instrument = instrument
        self._measurement = measurement
        self._storage = storage
        self._config = config
        self._router = router
        self._status_cb = status_cb
        self._sample_cb = sample_cb
        self._instrument_profile = instrument_profile or get_default_instrument_profile()
        self._running = False
        self._stop_event = threading.Event()
        self._stats = AcquisitionStats()
        self._fatal_error: Optional[str] = None
        self._mode = "software"
        self._overflow_monitoring = False
        self._stop_on_overflow = False
        self._completion_poll = False
        self._custom_started = False
        self._custom_event: TriggerEvent | None = None
        self._last_overflow_poll = 0.0
        self._last_completion_poll = 0.0

    @property
    def stats(self) -> AcquisitionStats:
        return self._stats

    @property
    def fatal_error(self) -> Optional[str]:
        return self._fatal_error

    @property
    def ok(self) -> bool:
        if self._fatal_error is not None:
            return False
        if self._stats.overflow_monitoring == "failed":
            return False
        if self._stats.overflow_detected:
            return False
        if self._stats.final_drain_complete is False:
            return False
        if (
            self._stats.expected_readings is not None
            and self._stats.data_integrity == "incomplete"
        ):
            return False
        return True

    def result_fields(self) -> dict[str, object]:
        return {
            "trigger_count_infinite": self._stats.trigger_count_infinite,
            "expected_readings": self._stats.expected_readings,
            "overflow_monitoring": self._stats.overflow_monitoring,
            "overflow_detected": self._stats.overflow_detected,
            "stop_reason": self._stats.stop_reason,
            "final_drain_complete": self._stats.final_drain_complete,
            "data_integrity": self._stats.data_integrity,
        }

    @property
    def result_reason(self) -> str:
        if self._fatal_error is not None:
            return "fatal_error"
        if self._stats.overflow_monitoring == "failed":
            return "overflow_monitor_failed"
        if self._stats.overflow_detected:
            return "overflow_detected"
        if self._stats.final_drain_complete is False:
            return "final_drain_incomplete"
        if (
            self._stats.expected_readings is not None
            and self._stats.data_integrity == "incomplete"
        ):
            return "incomplete"
        return self._stats.stop_reason

    def _emit(self, text: str) -> None:
        if self._status_cb:
            self._status_cb(text)

    def _emit_capture_status(self, sample: MeasurementSample) -> None:
        self._emit(f"captured={self._stats.captured} {_format_status_value(sample)}")

    def _emit_sample(self, sample: MeasurementSample) -> None:
        if self._sample_cb is not None:
            self._sample_cb(sample, self._stats.captured)

    def _handle_hardware_status_poll_timeout(self, count: int, exc: Exception) -> None:
        if count == 5:
            self._emit(
                "hardware status poll timeout warning "
                f"count={count} type={type(exc).__name__}"
            )
        elif count >= 25 and count % 25 == 0:
            self._stats.errors += 1
            self._emit(
                "hardware status polling degraded "
                f"count={count} errors={self._stats.errors} "
                f"type={type(exc).__name__}"
            )

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
        self.stop("fatal_error")

    def run(
        self,
        trigger_mode: str = "software",
        enable_hardware_trigger: bool = False,
        hardware_trigger_slope: str = "NEG",
    ) -> None:
        self._running = True
        self._stop_event.clear()
        self._fatal_error = None
        self._stats = AcquisitionStats()
        self._custom_started = False
        self._custom_event = None
        self._last_overflow_poll = 0.0
        self._last_completion_poll = 0.0
        mode = self._resolve_trigger_mode(trigger_mode, enable_hardware_trigger)
        self._mode = mode
        custom_mode = mode in ("immediate-custom", "software-custom", "external-custom")
        self._stats.trigger_count_infinite = bool(
            custom_mode and self._config.trigger_count_infinite
        )
        self._overflow_monitoring = bool(
            custom_mode
            and (
                self._config.monitor_overflow
                or self._config.trigger_count_infinite
                or self._config.stop_on_overflow
            )
        )
        self._stop_on_overflow = bool(custom_mode and self._config.stop_on_overflow)
        self._completion_poll = bool(
            self._overflow_monitoring and not self._config.trigger_count_infinite
        )
        if self._overflow_monitoring:
            self._stats.overflow_monitoring = "starting"
            self._stats.overflow_detected = None
        timer_interval_s = self._config.timer_interval_s
        timer_active = timer_interval_s is not None
        if custom_mode:
            capabilities = self._instrument_profile
            if not capabilities.supports_buffered_reading_memory:
                raise ValueError(f"{capabilities.model} does not support buffered reading memory")
            if mode == "software-custom" and not capabilities.supports_bus_trigger:
                raise ValueError(f"{capabilities.model} does not support bus trigger")
            if mode == "external-custom" and not capabilities.supports_external_trigger:
                raise ValueError(f"{capabilities.model} does not support external trigger")
            if self._config.trigger_count_infinite:
                if self._config.trigger_count is not None:
                    raise ValueError(
                        f"{mode} cannot combine trigger_count with trigger_count_infinite"
                    )
            elif self._config.trigger_count is None:
                raise ValueError(f"{mode} mode requires trigger_count")
            if self._config.sample_count is None:
                raise ValueError(f"{mode} mode requires sample_count")
            if not self._config.trigger_count_infinite:
                memory_limit = capabilities.reading_memory_limit
                expected_readings = self._config.trigger_count * self._config.sample_count
                self._stats.expected_readings = expected_readings
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
        if self._storage is not None:
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
        if self._overflow_monitoring and not self._begin_overflow_monitoring():
            if self._storage is not None:
                self._storage.close()
            self._emit("recording stopped")
            return
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
                            status_poll_timeout_cb=self._handle_hardware_status_poll_timeout,
                        )
                    except TimeoutError:
                        # No external edge within the timeout window; keep waiting.
                        if self._running:
                            hw.recover_from_timeout()
                            self._emit(
                                "hardware trigger wait timed out; re-armed and waiting for next edge"
                            )
                        continue
                    except Exception as exc:
                        if self._running:
                            self._stats.errors += 1
                            self._emit(
                                "hardware trigger wait error "
                                f"count={self._stats.errors} "
                                f"type={type(exc).__name__}: {exc}"
                            )
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
                    self.stop("max_samples_reached")
                if timer_active and self._running and not self._stop_event.is_set():
                    self._wait_timer_interval(timer_interval_s)
        finally:
            if custom_mode:
                self._finalize_custom_capture()
            elif self._stop_event.is_set():
                self._abort_measurement()
            if self._storage is not None:
                self._storage.close()
            self._emit("recording stopped")

    def _new_custom_event(
        self,
        source: TriggerSource,
        trigger_count: int | None,
        sample_count: int,
    ) -> TriggerEvent:
        trigger_count_label = (
            "infinity" if trigger_count is None else str(trigger_count)
        )
        expected_readings_label = (
            "unbounded"
            if trigger_count is None
            else str(trigger_count * sample_count)
        )
        return TriggerEvent.new(
            source,
            {
                "trigger_count": trigger_count_label,
                "sample_count": str(sample_count),
                "expected_readings": expected_readings_label,
                "time_basis": "pc_data_remove_time_not_instrument_sample_time",
            },
        )

    def _format_trigger_count(self, trigger_count: int | None) -> str:
        return "infinity" if trigger_count is None else str(trigger_count)

    def _format_expected_readings(self, expected_readings: int | None) -> str:
        return "unbounded" if expected_readings is None else str(expected_readings)

    def _begin_overflow_monitoring(self) -> bool:
        try:
            self._measurement.clear_questionable_events(self._instrument)
        except Exception as exc:
            self._mark_overflow_monitoring_failed(exc)
            return False
        self._stats.overflow_monitoring = "active"
        self._stats.overflow_detected = False
        self._emit("overflow monitoring active")
        return True

    def _mark_overflow_monitoring_failed(self, exc: Exception) -> None:
        if self._stats.overflow_monitoring == "failed":
            return
        self._stats.overflow_monitoring = "failed"
        self._stats.overflow_detected = None
        self._stats.errors += 1
        self._emit(
            "overflow monitoring failed "
            f"type={type(exc).__name__}: {exc}"
        )
        self.stop("overflow_monitor_failed")

    def _latch_overflow(self) -> None:
        if self._stats.overflow_detected:
            return
        self._stats.overflow_detected = True
        self._emit("overflow detected: questionable status bit 0x4000")
        if self._stop_on_overflow:
            self.stop("overflow_detected")

    def _poll_overflow_due(self) -> bool:
        if not self._overflow_monitoring:
            return True
        now = time.monotonic()
        if now - self._last_overflow_poll < 0.1:
            return True
        self._last_overflow_poll = now
        try:
            asserted = self._measurement.overflow_status_asserted(self._instrument)
        except Exception as exc:
            if not self._running:
                return False
            self._mark_overflow_monitoring_failed(exc)
            return False
        if asserted:
            self._latch_overflow()
        return self._running and not self._stop_event.is_set()

    def _completion_done_due(self) -> bool:
        now = time.monotonic()
        if now - self._last_completion_poll < 0.1:
            return False
        self._last_completion_poll = now
        try:
            return self._measurement.standard_event_complete(self._instrument)
        except Exception as exc:
            if not self._running:
                return False
            self._stats.errors += 1
            self._fatal_error = (
                f"completion verification failure: {type(exc).__name__}: {exc}"
            )
            self._emit(
                "completion verification failed "
                f"type={type(exc).__name__}: {exc}"
            )
            self.stop("fatal_error")
            return False

    def _prepare_completion_poll(self) -> bool:
        try:
            self._measurement.clear_standard_event(self._instrument)
        except Exception as exc:
            self._stats.errors += 1
            self._fatal_error = (
                f"completion verification failure: {type(exc).__name__}: {exc}"
            )
            self._emit(
                "completion verification failed "
                f"type={type(exc).__name__}: {exc}"
            )
            self.stop("fatal_error")
            return False
        return True

    def _request_operation_complete(self) -> bool:
        try:
            self._measurement.request_operation_complete(self._instrument)
        except Exception as exc:
            self._stats.errors += 1
            self._fatal_error = (
                f"completion verification failure: {type(exc).__name__}: {exc}"
            )
            self._emit(
                "completion verification failed "
                f"type={type(exc).__name__}: {exc}"
            )
            self.stop("fatal_error")
            return False
        return True

    def _capture_immediate_custom(
        self,
        trigger_count: int | None,
        sample_count: int,
    ) -> None:
        expected_readings = (
            None if trigger_count is None else trigger_count * sample_count
        )
        event = self._new_custom_event(
            TriggerSource.IMMEDIATE_CUSTOM,
            trigger_count,
            sample_count,
        )
        self._custom_event = event
        self._measurement.configure_immediate_custom(
            self._instrument,
            self._config,
            trigger_count,
            sample_count,
        )
        self._emit(
            "immediate custom capture configured "
            f"trigger_count={self._format_trigger_count(trigger_count)} "
            f"sample_count={sample_count} "
            f"expected_readings={self._format_expected_readings(expected_readings)}"
        )
        if self._completion_poll and not self._prepare_completion_poll():
            return
        self._measurement.start_buffered_capture(self._instrument)
        self._custom_started = True
        if self._completion_poll and not self._request_operation_complete():
            return
        self._emit("immediate custom capture started")
        self._drain_buffered_custom_capture(event, expected_readings)

    def _capture_software_custom(
        self,
        trigger_count: int | None,
        sample_count: int,
    ) -> None:
        expected_readings = (
            None if trigger_count is None else trigger_count * sample_count
        )
        event = self._new_custom_event(
            TriggerSource.SOFTWARE_CUSTOM,
            trigger_count,
            sample_count,
        )
        self._custom_event = event
        self._measurement.configure_software_custom(
            self._instrument,
            self._config,
            trigger_count,
            sample_count,
        )
        self._emit(
            "software custom capture configured "
            f"trigger_count={self._format_trigger_count(trigger_count)} "
            f"sample_count={sample_count} "
            f"expected_readings={self._format_expected_readings(expected_readings)}"
        )
        if self._completion_poll and not self._prepare_completion_poll():
            return
        self._measurement.start_buffered_capture(self._instrument)
        self._custom_started = True
        if self._completion_poll and not self._request_operation_complete():
            return
        self._emit("software custom capture armed")

        triggers_sent = 0
        waiting_trigger_emitted = False
        while (
            self._running
            and not self._stop_event.is_set()
            and (
                expected_readings is None
                or self._stats.captured < expected_readings
                or self._completion_poll
            )
        ):
            try:
                if not self._poll_overflow_due():
                    return
                available = self._measurement.buffered_points_available(self._instrument)
                observed_readings = self._stats.captured + available
                remaining = (
                    expected_readings - self._stats.captured
                    if expected_readings is not None
                    else available
                )
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
                        if self._storage is not None:
                            self._storage.write(sample)
                        self._stats.captured += 1
                        self._emit_sample(sample)
                    self._emit_capture_status(samples[-1])
                    continue

                if (
                    self._completion_poll
                    and triggers_sent > 0
                    and self._completion_done_due()
                ):
                    if not self._drain_remaining_custom(
                        event,
                        expected_readings=expected_readings,
                    ):
                        return
                    self._finish_custom_run(expected_readings)
                    return

                ready_for_next_trigger = (
                    True
                    if self._overflow_monitoring
                    else observed_readings >= triggers_sent * sample_count
                )
                can_send_trigger = (
                    trigger_count is None or triggers_sent < trigger_count
                )
                if can_send_trigger and ready_for_next_trigger:
                    ev = self._router.wait(
                        timeout_s=min(
                            self._config.trigger_timeout_ms / 1000.0,
                            0.2,
                        )
                    )
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
                    if self._overflow_monitoring and not self._wait_software_trigger_ready():
                        return
                    self._measurement.send_bus_trigger(self._instrument)
                    triggers_sent += 1
                    self._emit(
                        "software custom trigger sent="
                        f"{triggers_sent}/{self._format_trigger_count(trigger_count)}"
                    )
                    continue

                self._stop_event.wait(0.05)
            except Exception as exc:
                if not self._running:
                    return
                self._record_capture_failure("buffered capture", exc)
                return
        if expected_readings is not None and self._stats.captured >= expected_readings:
            self._finish_custom_run(expected_readings)

    def _wait_software_trigger_ready(self) -> bool:
        while self._running and not self._stop_event.is_set():
            if not self._poll_overflow_due():
                return False
            try:
                if self._measurement.software_trigger_ready(self._instrument):
                    return True
            except Exception as exc:
                if not self._running:
                    return False
                self._record_capture_failure("software trigger readiness", exc)
                return False
            self._stop_event.wait(0.05)
        return False

    def _capture_external_custom(
        self,
        trigger_count: int | None,
        sample_count: int,
        slope: str,
    ) -> None:
        expected_readings = (
            None if trigger_count is None else trigger_count * sample_count
        )
        event = self._new_custom_event(
            TriggerSource.EXTERNAL_CUSTOM,
            trigger_count,
            sample_count,
        )
        self._custom_event = event
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
            f"trigger_count={self._format_trigger_count(trigger_count)} "
            f"sample_count={sample_count} "
            f"expected_readings={self._format_expected_readings(expected_readings)} "
            f"slope={str(slope).upper()} "
            f"delay_s={self._config.hw_trigger_delay_s}"
        )
        if self._completion_poll and not self._prepare_completion_poll():
            return
        self._measurement.start_buffered_capture(self._instrument)
        self._custom_started = True
        if self._completion_poll and not self._request_operation_complete():
            return
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
        expected_readings: int | None,
        poll_control_events: bool = False,
        ignored_software_trigger_status: Optional[str] = None,
    ) -> None:
        while (
            self._running
            and not self._stop_event.is_set()
            and (
                expected_readings is None
                or self._stats.captured < expected_readings
                or self._completion_poll
            )
        ):
            try:
                if not self._poll_overflow_due():
                    return
                available = self._measurement.buffered_points_available(self._instrument)
                remaining = (
                    expected_readings - self._stats.captured
                    if expected_readings is not None
                    else available
                )
                read_count = min(available, remaining)
                if self._config.buffer_drain_size is not None:
                    read_count = min(read_count, self._config.buffer_drain_size)
                if read_count <= 0:
                    if self._completion_poll and self._completion_done_due():
                        if not self._drain_remaining_custom(
                            event,
                            expected_readings=expected_readings,
                            poll_control_events=poll_control_events,
                            ignored_software_trigger_status=ignored_software_trigger_status,
                        ):
                            return
                        self._finish_custom_run(expected_readings)
                        return
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
                    if self._storage is not None:
                        self._storage.write(sample)
                    self._stats.captured += 1
                    self._emit_sample(sample)
                self._emit_capture_status(samples[-1])
            except Exception as exc:
                if not self._running:
                    return
                self._record_capture_failure("buffered capture", exc)
                return
            if poll_control_events and not self._drain_custom_control_events(ignored_software_trigger_status):
                return
        if expected_readings is not None and self._stats.captured >= expected_readings:
            self._finish_custom_run(expected_readings)

    def _drain_remaining_custom(
        self,
        event: TriggerEvent,
        *,
        expected_readings: int | None,
        poll_control_events: bool = False,
        ignored_software_trigger_status: Optional[str] = None,
        final: bool = False,
        deadline: float | None = None,
    ) -> bool:
        _ = expected_readings
        while final or (self._running and not self._stop_event.is_set()):
            if deadline is not None and time.monotonic() >= deadline:
                if final:
                    self._emit("final drain budget exhausted")
                return False
            if not final and not self._poll_overflow_due():
                return False
            try:
                if deadline is not None and time.monotonic() >= deadline:
                    if final:
                        self._emit("final drain budget exhausted")
                    return False
                available = self._measurement.buffered_points_available(self._instrument)
                if available <= 0:
                    return True
                read_count = available
                if self._config.buffer_drain_size is not None:
                    read_count = min(read_count, self._config.buffer_drain_size)
                samples = self._measurement.read_buffered_samples(
                    self._instrument,
                    event,
                    read_count,
                    first_sample_index=self._stats.captured,
                )
                for sample in samples:
                    if self._storage is not None:
                        self._storage.write(sample)
                    self._stats.captured += 1
                    self._emit_sample(sample)
                if samples:
                    self._emit_capture_status(samples[-1])
            except Exception as exc:
                if final:
                    self._emit(
                        "final drain failed "
                        f"type={type(exc).__name__}: {exc}"
                    )
                    return False
                if not self._running:
                    return False
                self._record_capture_failure("buffered capture", exc)
                return False
            if poll_control_events and not self._drain_custom_control_events(
                ignored_software_trigger_status
            ):
                return False
        return False

    def _finish_custom_run(self, expected_readings: int | None) -> None:
        if expected_readings is not None:
            self._emit(f"expected readings reached: {expected_readings}")
        self.stop("completed")

    def _finalize_custom_capture(self) -> None:
        if not self._custom_started:
            return
        self._abort_measurement()
        if self._overflow_monitoring and self._stats.overflow_monitoring == "active":
            try:
                if self._measurement.overflow_status_asserted(self._instrument):
                    self._latch_overflow()
            except Exception as exc:
                self._mark_overflow_monitoring_failed(exc)
        if self._custom_event is not None:
            self._stats.final_drain_complete = self._drain_remaining_custom(
                self._custom_event,
                expected_readings=self._stats.expected_readings,
                final=True,
                deadline=time.monotonic() + 2.0,
            )
        self._set_data_integrity()

    def _set_data_integrity(self) -> None:
        if not self._custom_started:
            return
        if self._stats.overflow_monitoring == "failed":
            self._stats.data_integrity = "unknown"
        elif self._stats.overflow_detected:
            self._stats.data_integrity = "incomplete"
        elif self._stats.expected_readings is None:
            self._stats.data_integrity = "unknown"
        elif self._stats.captured == self._stats.expected_readings:
            self._stats.data_integrity = "no_loss_detected"
        else:
            self._stats.data_integrity = "incomplete"

    def _capture(self, event: TriggerEvent) -> None:
        try:
            sample = self._measurement.read_sample(self._instrument, event)
            if self._storage is not None:
                self._storage.write(sample)
            self._stats.captured += 1
            self._emit_sample(sample)
            self._emit_capture_status(sample)
        except Exception as exc:
            if not self._running:
                return
            self._record_capture_failure("capture", exc)

    def stop(self, reason: str = "stop_requested") -> None:
        if self._stats.stop_reason == "unknown":
            self._stats.stop_reason = reason
        self._running = False
        self._stop_event.set()

    def _handle_control_event(self, event: TriggerEvent) -> bool:
        if event.metadata.get("control") != "stop":
            return False
        self._emit("stop request received")
        self._abort_measurement()
        self.stop("stop_requested")
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
