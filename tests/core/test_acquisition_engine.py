from __future__ import annotations

import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from meters_tool_core.acquisition import TriggerAcquisitionEngine
from meters_tool_core.instrument import VisaInstrument
from meters_tool_core.measurement import CurrentMeasurement, VoltageDcRatioMeasurement
from meters_tool_core.models import (
    AcquisitionConfig,
    InstrumentConfig,
    InstrumentProfile,
    TriggerEvent,
    TriggerSource,
)
from meters_tool_core.trigger import TriggerRouter

from core_test_helpers import (
    BufferedAvailableFailingMeasurement,
    BufferedReadFailingMeasurement,
    CaptureFailingMeasurement,
    CapturingStorage,
    FakeBufferedMeasurement,
    FakeInstrument,
    FailingMeasurement,
    FakeMeasurement,
    FakeStorage,
    PermissionDeniedStorage,
    RecordingInstrument,
    make_acquisition_engine,
)


FAKE_NO_BUFFER_PROFILE = InstrumentProfile(
    vendor="Fake",
    model="NO_BUFFER",
    model_id="fake-no-buffer",
    aliases=("NO_BUFFER",),
    reading_memory_limit=5,
    supported_measurement_types=("current_dc",),
    supports_buffered_reading_memory=False,
    supports_bus_trigger=False,
    supports_external_trigger=False,
    supports_sample_timer=False,
)

FAKE_SMALL_BUFFER_PROFILE = InstrumentProfile(
    vendor="Fake",
    model="SMALL_BUFFER",
    model_id="fake-small-buffer",
    aliases=("SMALL_BUFFER",),
    reading_memory_limit=5,
    supported_measurement_types=("current_dc",),
    supports_buffered_reading_memory=True,
    supports_bus_trigger=True,
    supports_external_trigger=True,
    supports_sample_timer=False,
)


class AlwaysTimeoutHardwareInstrument(FakeInstrument):
    def __init__(self) -> None:
        super().__init__()
        self.commands: list[str] = []
        self._stb_reads = 0

    def set_timeout_ms(self, timeout_ms: int) -> None:  # noqa: ARG002
        return

    def read_status_byte(self) -> int:
        self._stb_reads += 1
        return 0

    def poll_system_error(self) -> str:
        return "0,No error"

    def write(self, command: str) -> None:
        self.commands.append(command)


class FailingStatusHardwareInstrument(AlwaysTimeoutHardwareInstrument):
    def read_status_byte(self) -> int:
        raise RuntimeError("stb failed")


class OverflowAssertingMeasurement(FakeBufferedMeasurement):
    def __init__(self) -> None:
        super().__init__()
        self.overflow_asserted = True


class OverflowFailingMeasurement(FakeBufferedMeasurement):
    def overflow_status_asserted(self, instrument):  # noqa: ANN001, ARG002
        raise RuntimeError("questionable status failed")


class PostAbortDrainMeasurement(FakeBufferedMeasurement):
    def __init__(self, instrument: RecordingInstrument) -> None:
        super().__init__()
        self.instrument = instrument

    def buffered_points_available(self, instrument):  # noqa: ANN001, ARG002
        if self.instrument.abort_count == 0:
            return 0
        return self.sample_count


class WaitingExternalBufferedMeasurement(FakeBufferedMeasurement):
    def configure_external_custom(self, instrument, config, trigger_count, sample_count, slope, delay_s):  # noqa: ANN001, ARG002
        self.sample_count = 0
        slope_cmd = "POS" if str(slope).upper() == "POS" else "NEG"
        instrument.write("TRIG:SOUR EXT")
        instrument.write(f"TRIG:SLOP {slope_cmd}")
        instrument.write(f"TRIG:COUNT {trigger_count}")
        instrument.write(f"SAMP:COUNT {sample_count}")
        instrument.write(f"TRIG:DEL {max(0.0, float(delay_s))}")


class AcquisitionEngineTests(unittest.TestCase):
    def test_custom_abort_failure_cannot_report_successful_drain(self):
        for failure in (None, RuntimeError("ABOR failed")):
            with self.subTest(failure=failure), patch.object(
                RecordingInstrument, "abort_measurement", return_value=False, side_effect=failure
            ):
                storage = CapturingStorage()
                engine = make_acquisition_engine(
                    instrument=RecordingInstrument(),
                    measurement=FakeBufferedMeasurement(),
                    storage=storage,
                    config=AcquisitionConfig(trigger_timeout_ms=50, trigger_count=1, sample_count=1),
                )

                engine.run(trigger_mode="immediate-custom")

                self.assertFalse(engine.ok)
                self.assertEqual("measurement abort failed", engine.fatal_error)
                self.assertFalse(engine.stats.final_drain_complete)
                self.assertEqual(1, engine.stats.captured)
                self.assertEqual(1, len(storage.samples))
                self.assertNotEqual("no_loss_detected", engine.stats.data_integrity)

    def test_finalization_budget_covers_abort_status_and_drain_without_changing_visa_timeout(self):
        for slow_command, latched, expected_commands in (
            ("ABOR", False, ["ABOR"]),
            ("STAT:QUES:EVEN?", False, ["ABOR", "STAT:QUES:EVEN?"]),
            ("STAT:QUES:COND?", False, ["ABOR", "STAT:QUES:EVEN?", "STAT:QUES:COND?"]),
            ("STAT:QUES:EVEN?", True, ["ABOR", "STAT:QUES:EVEN?"]),
            ("DATA:POINts?", False, ["ABOR", "STAT:QUES:EVEN?", "STAT:QUES:COND?", "DATA:POINts?"]),
        ):
            with self.subTest(slow_command=slow_command, latched=latched):
                now = [0.0]

                class Session:
                    def __init__(self):
                        self.commands = []
                        self.timeouts = []
                        self.aborted = False

                    @property
                    def timeout(self):
                        return self.timeouts[-1]

                    @timeout.setter
                    def timeout(self, value):
                        self.timeouts.append(value)

                    def write(self, command):
                        if command == "ABOR":
                            self.aborted = True
                        self.commands.append(command)
                        if self.aborted and command == slow_command:
                            now[0] += 2.1

                    def query(self, command):
                        self.write(command)
                        if self.aborted:
                            now[0] += 0.1
                        if command == "*IDN?":
                            return "Keysight Technologies,34461A,FAKE,1.0"
                        return "1" if command == "DATA:POINts?" else "0"

                session = Session()
                instrument = VisaInstrument(
                    InstrumentConfig(resource_string="SIM::34461A", timeout_ms=1000),
                    resource_manager_factory=lambda: SimpleNamespace(open_resource=lambda _: session),
                )
                instrument.connect()

                def stop_when_armed(message):
                    if message == "software custom capture armed":
                        if latched:
                            engine._latch_overflow()
                        engine.stop()

                engine = make_acquisition_engine(
                    instrument=instrument, measurement=CurrentMeasurement(),
                    config=AcquisitionConfig(trigger_count_infinite=True, sample_count=1),
                    status_cb=stop_when_armed,
                )
                with patch("meters_tool_core.acquisition.time.monotonic", side_effect=lambda: now[0]):
                    engine.run(trigger_mode="software-custom")

                self.assertEqual(expected_commands, session.commands[session.commands.index("ABOR"):])
                self.assertEqual([1000], session.timeouts)
                self.assertEqual(1000, session.timeout)
                self.assertFalse(engine.ok)
                self.assertFalse(engine.stats.final_drain_complete)
                self.assertNotEqual("no_loss_detected", engine.stats.data_integrity)
                if slow_command in ("ABOR", "STAT:QUES:EVEN?"):
                    self.assertEqual("failed", engine.stats.overflow_monitoring)
                    self.assertIs(engine.stats.overflow_detected, True if latched else None)

    def test_confirmed_overflow_remains_latched_after_monitor_failure(self):
        class FailingAfterOverflow(FakeBufferedMeasurement):
            polls = 0

            def overflow_status_asserted(self, instrument):  # noqa: ANN001, ARG002
                self.polls += 1
                if self.polls == 1:
                    return True
                raise TimeoutError("monitor timed out")

        engine = make_acquisition_engine(
            measurement=FailingAfterOverflow(),
            config=AcquisitionConfig(trigger_count_infinite=True, sample_count=1),
        )

        engine.run(trigger_mode="software-custom")

        self.assertTrue(engine.stats.overflow_detected)
        self.assertEqual("failed", engine.stats.overflow_monitoring)
        self.assertEqual("incomplete", engine.stats.data_integrity)
        self.assertEqual("overflow_monitor_failed", engine.result_reason)

    def test_ratio_final_drain_applies_deadline_to_each_query(self):
        now = [0.0]

        class SlowRatioInstrument(RecordingInstrument):
            def query(self, command: str) -> str:
                self.commands.append(command)
                now[0] += 0.6
                return {"DATA:POINts?": "3", "DATA:REMove? 1": "1", "DATA2?": "1,1"}[command]

            def set_timeout_ms(self, timeout_ms: int) -> None:
                self.asserted_timeouts.append(timeout_ms)

        for deadline, captured in ((1.0, 0), (3.0, 2)):
            with self.subTest(deadline=deadline):
                now[0] = 0.0
                instrument = SlowRatioInstrument()
                instrument.asserted_timeouts = []
                measurement = VoltageDcRatioMeasurement()
                measurement.configure(instrument, AcquisitionConfig())
                instrument.commands.clear()
                storage = CapturingStorage()
                emitted = []
                engine = TriggerAcquisitionEngine(
                    instrument=instrument, measurement=measurement, storage=storage,
                    config=AcquisitionConfig(), router=TriggerRouter(),
                    sample_cb=lambda sample, count: emitted.append((sample, count)),
                )

                with patch("meters_tool_core.acquisition.time.monotonic", side_effect=lambda: now[0]):
                    complete = engine._drain_remaining_custom(
                        TriggerEvent.new(TriggerSource.IMMEDIATE_CUSTOM),
                        expected_readings=None, final=True, deadline=deadline,
                    )

                self.assertFalse(complete)
                expected_commands = ["DATA:POINts?", "DATA:REMove? 1"] if not captured else [
                    "DATA:POINts?", "DATA:REMove? 1", "DATA2?", "DATA:REMove? 1", "DATA2?",
                ]
                self.assertEqual(expected_commands, instrument.commands)
                self.assertEqual(captured, engine.stats.captured)
                self.assertEqual(storage.samples, [sample for sample, _ in emitted])
                self.assertEqual(captured, len(storage.samples))
                self.assertEqual(list(range(1, captured + 1)), [count for _, count in emitted])
                self.assertEqual([], instrument.asserted_timeouts)

    def test_finite_custom_stop_preserves_captured_rows_without_monitoring(self):
        storage = CapturingStorage()
        engine = make_acquisition_engine(
            instrument=RecordingInstrument(), measurement=FakeBufferedMeasurement(),
            storage=storage,
            config=AcquisitionConfig(trigger_count=1, sample_count=3, buffer_drain_size=1),
            status_cb=lambda message: engine.stop() if message.startswith("captured=") else None,
        )

        engine.run(trigger_mode="immediate-custom")

        self.assertEqual(1, engine.stats.captured)
        self.assertEqual(1, len(storage.samples))
        self.assertIsNone(engine.stats.final_drain_complete)
        self.assertTrue(engine.ok)
        self.assertEqual("stop_requested", engine.stats.stop_reason)
        self.assertEqual("incomplete", engine.stats.data_integrity)

    def test_ratio_final_drain_persists_completed_pairs_before_later_query_failure(self):
        for failed_command, expected in ((None, 2), ("DATA:REMove? 1", 1), ("DATA2?", 1)):
            with self.subTest(failed_command=failed_command):
                now = [0.0]

                class RatioInstrument(RecordingInstrument):
                    remaining = 3
                    removes = 0

                    def query(self, command):
                        self.commands.append(command)
                        if command.startswith("STAT:QUES:"):
                            return "0"
                        if command == "DATA:POINts?":
                            return str(self.remaining)
                        if command == "DATA:REMove? 1":
                            self.removes += 1
                        if command == failed_command and self.removes == 2:
                            raise OSError("synthetic ratio query failure")
                        now[0] += 0.5
                        if command == "DATA:REMove? 1":
                            self.remaining -= 1
                            return "2"
                        if command == "DATA2?":
                            return "4,2"
                        raise AssertionError(command)

                storage = CapturingStorage()
                emitted = []
                engine = TriggerAcquisitionEngine(
                    instrument=RatioInstrument(), measurement=VoltageDcRatioMeasurement(),
                    storage=storage,
                    config=AcquisitionConfig(trigger_count_infinite=True, sample_count=1),
                    router=TriggerRouter(),
                    status_cb=lambda message: engine.stop() if message == "software custom capture armed" else None,
                    sample_cb=lambda sample, count: emitted.append((sample, count)),
                )
                with patch("meters_tool_core.acquisition.time.monotonic", side_effect=lambda: now[0]):
                    engine.run(trigger_mode="software-custom")

                self.assertFalse(engine.ok)
                self.assertFalse(engine.stats.final_drain_complete)
                self.assertEqual(expected, engine.stats.captured)
                self.assertEqual([2.0] * expected, [sample.value for sample in storage.samples])
                self.assertEqual(storage.samples, [sample for sample, _ in emitted])
                self.assertEqual(list(range(1, expected + 1)), [count for _, count in emitted])

    def test_priority_stop_interrupts_continuous_custom_drain(self):
        for mode in ("immediate-custom", "software-custom", "external-custom"):
            with self.subTest(mode=mode):
                instrument = RecordingInstrument()

                class ContinuousMeasurement(FakeBufferedMeasurement):
                    def buffered_points_available(self, backend):
                        return 0 if instrument.abort_count else 1

                router = TriggerRouter()
                pending = TriggerEvent.new(TriggerSource.SOFTWARE)
                router.publish(pending)
                storage = CapturingStorage()

                def stop_after_first(message):
                    if not message.startswith("captured="):
                        return
                    if engine.stats.captured == 1:
                        router.publish(TriggerEvent.new(TriggerSource.SOFTWARE, {"control": "stop"}))
                    elif engine.stats.captured == 5:
                        engine.stop("probe_bound")

                engine = make_acquisition_engine(
                    instrument=instrument, measurement=ContinuousMeasurement(),
                    storage=storage, router=router,
                    config=AcquisitionConfig(trigger_count_infinite=True, sample_count=1),
                    status_cb=stop_after_first,
                )
                engine.run(trigger_mode=mode)

                self.assertEqual("stop_requested", engine.stats.stop_reason)
                self.assertEqual(1, engine.stats.captured)
                self.assertIsNone(router.poll_control())
                if mode == "software-custom":
                    self.assertIs(pending, router.wait(0))

    def test_priority_stop_interrupts_bus_readiness_wait(self):
        readiness_checked = threading.Event()

        class NotReadyMeasurement(FakeBufferedMeasurement):
            def software_trigger_ready(self, instrument):  # noqa: ANN001, ARG002
                readiness_checked.set()
                return False

        measurement = NotReadyMeasurement()
        router = TriggerRouter()
        engine = make_acquisition_engine(
            instrument=RecordingInstrument(), measurement=measurement, router=router,
            config=AcquisitionConfig(trigger_count=1, sample_count=1, monitor_overflow=True),
        )
        worker = threading.Thread(target=engine.run, kwargs={"trigger_mode": "software-custom"})
        worker.start()
        try:
            router.publish(TriggerEvent.new(TriggerSource.SOFTWARE))
            self.assertTrue(readiness_checked.wait(1))
            router.publish(TriggerEvent.new(TriggerSource.SOFTWARE, {"control": "stop"}))
            worker.join(timeout=1)
            self.assertFalse(worker.is_alive())
            self.assertEqual(0, measurement.bus_triggers_sent)
            self.assertEqual("stop_requested", engine.stats.stop_reason)
        finally:
            engine.stop()
            worker.join(timeout=1)

    def test_final_drain_does_not_read_after_points_query_uses_budget(self):
        now = [0.0]

        class SlowPoints(FakeBufferedMeasurement):
            def buffered_points_available(self, instrument):  # noqa: ANN001, ARG002
                now[0] += 2.1
                return 1

            def read_buffered_samples(self, *args, **kwargs):  # noqa: ANN002, ANN003
                raise AssertionError("read issued after deadline")

        engine = make_acquisition_engine(measurement=SlowPoints())  # type: ignore[arg-type]
        event = TriggerEvent.new(TriggerSource.IMMEDIATE_CUSTOM)

        with patch("meters_tool_core.acquisition.time.monotonic", side_effect=lambda: now[0]):
            complete = engine._drain_remaining_custom(
                event, expected_readings=None, final=True, deadline=2.0
            )

        self.assertFalse(complete)

    def test_storage_open_permission_error_sets_fatal_error(self):
        engine = make_acquisition_engine(
            storage=PermissionDeniedStorage(),  # type: ignore[arg-type]
        )

        engine.run()

        self.assertEqual(0, engine.stats.captured)
        self.assertEqual(1, engine.stats.errors)
        self.assertIsNotNone(engine.fatal_error)
        self.assertIn("cannot open CSV output file: data\\locked.csv", engine.fatal_error)
        self.assertIn("file may be open in Excel", engine.fatal_error)

    def test_custom_mode_uses_profile_buffer_support(self):
        engine = make_acquisition_engine(
            instrument=RecordingInstrument(),  # type: ignore[arg-type]
            measurement=FakeBufferedMeasurement(),  # type: ignore[arg-type]
            config=AcquisitionConfig(trigger_timeout_ms=50, trigger_count=1, sample_count=1),
            instrument_profile=FAKE_NO_BUFFER_PROFILE,
        )

        with self.assertRaisesRegex(ValueError, "NO_BUFFER does not support buffered reading memory"):
            engine.run(trigger_mode="immediate-custom")

    def test_custom_mode_uses_profile_memory_limit(self):
        engine = make_acquisition_engine(
            instrument=RecordingInstrument(),  # type: ignore[arg-type]
            measurement=FakeBufferedMeasurement(),  # type: ignore[arg-type]
            config=AcquisitionConfig(trigger_timeout_ms=50, trigger_count=3, sample_count=2),
            instrument_profile=FAKE_SMALL_BUFFER_PROFILE,
        )

        with self.assertRaisesRegex(ValueError, "expected readings exceed 5 on the SMALL_BUFFER"):
            engine.run(trigger_mode="immediate-custom")

    def test_trigger_engine_captures_only_on_trigger(self):
        router = TriggerRouter()
        waiting = threading.Event()
        captured = threading.Event()

        def status_cb(status: str) -> None:
            if status == "waiting trigger":
                waiting.set()
            if status.startswith("captured=1 "):
                captured.set()

        engine = make_acquisition_engine(
            router=router,
            status_cb=status_cb,
        )
        worker = threading.Thread(target=engine.run)
        worker.start()
        try:
            self.assertTrue(waiting.wait(timeout=1.0), "worker did not enter trigger wait")
            self.assertEqual(0, engine.stats.captured)
            router.publish(TriggerEvent.new(TriggerSource.SOFTWARE))
            self.assertTrue(captured.wait(timeout=1.0), "worker did not capture the trigger")
        finally:
            engine.stop()
            worker.join(timeout=1)

        self.assertFalse(worker.is_alive())
        self.assertEqual(1, engine.stats.captured)

    def test_waiting_trigger_status_is_emitted_once_while_idle(self):
        class CountingTriggerRouter(TriggerRouter):
            def __init__(self) -> None:
                super().__init__()
                self.wait_calls = 0
                self.multiple_waits = threading.Event()

            def wait(self, timeout_s: float) -> TriggerEvent | None:
                self.wait_calls += 1
                if self.wait_calls >= 3:
                    self.multiple_waits.set()
                return super().wait(timeout_s)

        router = CountingTriggerRouter()
        statuses: list[str] = []
        waiting = threading.Event()

        def status_cb(status: str) -> None:
            statuses.append(status)
            if status == "waiting trigger":
                waiting.set()

        engine = make_acquisition_engine(
            router=router,
            status_cb=status_cb,
        )

        worker = threading.Thread(target=engine.run)
        worker.start()
        try:
            self.assertTrue(waiting.wait(timeout=1.0), "worker did not emit waiting trigger")
            self.assertTrue(
                router.multiple_waits.wait(timeout=1.0),
                "worker did not complete multiple idle waits",
            )
        finally:
            engine.stop()
            worker.join(timeout=1)

        self.assertFalse(worker.is_alive())
        self.assertEqual(1, statuses.count("waiting trigger"))

    def test_capture_status_includes_scaled_sample_value(self):
        statuses: list[str] = []
        engine = TriggerAcquisitionEngine(
            instrument=FakeInstrument(),  # type: ignore[arg-type]
            measurement=FakeMeasurement(value=0.0123, unit="A"),  # type: ignore[arg-type]
            storage=FakeStorage(),  # type: ignore[arg-type]
            config=AcquisitionConfig(trigger_timeout_ms=50, max_samples=1),
            router=TriggerRouter(),
            status_cb=statuses.append,
        )

        worker = threading.Thread(target=engine.run, kwargs={"trigger_mode": "immediate"})
        worker.start()
        worker.join(timeout=1)

        self.assertFalse(worker.is_alive())
        self.assertTrue(any("captured=1 value=12.3 mA" in s for s in statuses))

    def test_capture_status_scales_negative_microamps(self):
        statuses: list[str] = []
        engine = TriggerAcquisitionEngine(
            instrument=FakeInstrument(),  # type: ignore[arg-type]
            measurement=FakeMeasurement(value=-5e-7, unit="A"),  # type: ignore[arg-type]
            storage=FakeStorage(),  # type: ignore[arg-type]
            config=AcquisitionConfig(trigger_timeout_ms=50, max_samples=1),
            router=TriggerRouter(),
            status_cb=statuses.append,
        )

        worker = threading.Thread(target=engine.run, kwargs={"trigger_mode": "immediate"})
        worker.start()
        worker.join(timeout=1)

        self.assertFalse(worker.is_alive())
        self.assertTrue(any("captured=1 value=-0.5 uA" in s for s in statuses))

    def test_capture_status_formats_resistance_prefix(self):
        statuses: list[str] = []
        engine = TriggerAcquisitionEngine(
            instrument=FakeInstrument(),  # type: ignore[arg-type]
            measurement=FakeMeasurement(  # type: ignore[arg-type]
                value=12_300.0,
                unit="Ohm",
                measurement_type="resistance_2w",
            ),
            storage=FakeStorage(),  # type: ignore[arg-type]
            config=AcquisitionConfig(trigger_timeout_ms=50, max_samples=1),
            router=TriggerRouter(),
            status_cb=statuses.append,
        )

        worker = threading.Thread(target=engine.run, kwargs={"trigger_mode": "immediate"})
        worker.start()
        worker.join(timeout=1)

        self.assertFalse(worker.is_alive())
        self.assertTrue(any("captured=1 value=12.3 kOhm" in s for s in statuses))

    def test_simple_capture_exception_is_fatal_and_stops_worker(self):
        statuses: list[str] = []
        engine = TriggerAcquisitionEngine(
            instrument=FakeInstrument(),  # type: ignore[arg-type]
            measurement=CaptureFailingMeasurement(),  # type: ignore[arg-type]
            storage=FakeStorage(),  # type: ignore[arg-type]
            config=AcquisitionConfig(trigger_timeout_ms=50),
            router=TriggerRouter(),
            status_cb=statuses.append,
        )

        worker = threading.Thread(target=engine.run, kwargs={"trigger_mode": "immediate"})
        worker.start()
        worker.join(timeout=1)

        self.assertFalse(worker.is_alive())
        self.assertEqual(0, engine.stats.captured)
        self.assertEqual(1, engine.stats.errors)
        self.assertIsNotNone(engine.fatal_error)
        self.assertIn("capture failure", engine.fatal_error)
        self.assertTrue(any("capture error count=1" in s for s in statuses))

    def test_stop_only_sets_stop_state_without_instrument_io(self):
        instrument = FakeInstrument()
        router = TriggerRouter()
        engine = TriggerAcquisitionEngine(
            instrument=instrument,  # type: ignore[arg-type]
            measurement=FakeMeasurement(),  # type: ignore[arg-type]
            storage=FakeStorage(),  # type: ignore[arg-type]
            config=AcquisitionConfig(trigger_timeout_ms=50),
            router=router,
        )
        engine.stop()
        self.assertEqual(0, instrument.abort_count)

    def test_control_stop_event_aborts_from_worker_thread(self):
        instrument = FakeInstrument()
        router = TriggerRouter()
        engine = TriggerAcquisitionEngine(
            instrument=instrument,  # type: ignore[arg-type]
            measurement=FakeMeasurement(),  # type: ignore[arg-type]
            storage=FakeStorage(),  # type: ignore[arg-type]
            config=AcquisitionConfig(trigger_timeout_ms=50),
            router=router,
        )
        worker = threading.Thread(target=engine.run)
        worker.start()
        router.publish(TriggerEvent.new(TriggerSource.SOFTWARE, {"control": "stop"}))
        worker.join(timeout=1)
        self.assertFalse(worker.is_alive())
        self.assertGreaterEqual(instrument.abort_count, 1)

    def test_hardware_timeout_emits_rearmed_status_without_error(self):
        instrument = AlwaysTimeoutHardwareInstrument()
        router = TriggerRouter()
        statuses: list[str] = []
        engine = TriggerAcquisitionEngine(
            instrument=instrument,  # type: ignore[arg-type]
            measurement=FakeMeasurement(),  # type: ignore[arg-type]
            storage=FakeStorage(),  # type: ignore[arg-type]
            config=AcquisitionConfig(trigger_timeout_ms=100),
            router=router,
            status_cb=statuses.append,
        )
        worker = threading.Thread(
            target=engine.run,
            kwargs={"enable_hardware_trigger": True, "hardware_trigger_slope": "NEG"},
        )
        worker.start()
        time.sleep(0.35)
        engine.stop()
        worker.join(timeout=1)
        self.assertFalse(worker.is_alive())
        self.assertEqual(0, engine.stats.errors)
        self.assertTrue(
            any(
                "hardware trigger wait timed out; re-armed and waiting for next edge" in s
                for s in statuses
            )
        )

    def test_hardware_status_poll_timeout_thresholds_are_nonfatal_diagnostics(self):
        statuses: list[str] = []
        engine = TriggerAcquisitionEngine(
            instrument=AlwaysTimeoutHardwareInstrument(),  # type: ignore[arg-type]
            measurement=FakeMeasurement(),  # type: ignore[arg-type]
            storage=FakeStorage(),  # type: ignore[arg-type]
            config=AcquisitionConfig(trigger_timeout_ms=50),
            router=TriggerRouter(),
            status_cb=statuses.append,
        )
        exc = TimeoutError("status byte")

        engine._handle_hardware_status_poll_timeout(4, exc)
        self.assertEqual([], statuses)
        self.assertEqual(0, engine.stats.errors)

        engine._handle_hardware_status_poll_timeout(5, exc)
        self.assertTrue(
            any("hardware status poll timeout warning count=5 type=TimeoutError" in s for s in statuses)
        )
        self.assertEqual(0, engine.stats.errors)

        engine._handle_hardware_status_poll_timeout(25, exc)
        self.assertTrue(
            any("hardware status polling degraded count=25 errors=1 type=TimeoutError" in s for s in statuses)
        )
        self.assertEqual(1, engine.stats.errors)

        engine._handle_hardware_status_poll_timeout(50, exc)
        self.assertTrue(
            any("hardware status polling degraded count=50 errors=2 type=TimeoutError" in s for s in statuses)
        )
        self.assertEqual(2, engine.stats.errors)
        self.assertIsNone(engine.fatal_error)

    def test_non_timeout_hardware_wait_exception_is_nonfatal_error(self):
        instrument = FailingStatusHardwareInstrument()
        statuses: list[str] = []
        engine = TriggerAcquisitionEngine(
            instrument=instrument,  # type: ignore[arg-type]
            measurement=FakeMeasurement(),  # type: ignore[arg-type]
            storage=FakeStorage(),  # type: ignore[arg-type]
            config=AcquisitionConfig(trigger_timeout_ms=50),
            router=TriggerRouter(),
            status_cb=statuses.append,
        )

        worker = threading.Thread(
            target=engine.run,
            kwargs={"enable_hardware_trigger": True, "hardware_trigger_slope": "NEG"},
        )
        worker.start()
        deadline = time.monotonic() + 1.0
        while not any("hardware trigger wait error" in s for s in statuses):
            if time.monotonic() >= deadline:
                break
            time.sleep(0.01)
        engine.stop()
        worker.join(timeout=1)

        self.assertFalse(worker.is_alive())
        self.assertGreaterEqual(engine.stats.errors, 1)
        self.assertIsNone(engine.fatal_error)
        self.assertTrue(
            any(
                "hardware trigger wait error count=1 type=RuntimeError: stb failed" in s
                for s in statuses
            )
        )

    def test_software_trigger_is_ignored_in_hardware_mode(self):
        instrument = AlwaysTimeoutHardwareInstrument()
        router = TriggerRouter()
        statuses: list[str] = []
        recording_started = threading.Event()
        software_ignored = threading.Event()

        def status_cb(status: str) -> None:
            statuses.append(status)
            if status == "recording started":
                recording_started.set()
            if status == "software trigger ignored while hardware trigger is enabled":
                software_ignored.set()

        engine = TriggerAcquisitionEngine(
            instrument=instrument,  # type: ignore[arg-type]
            measurement=FailingMeasurement(),  # type: ignore[arg-type]
            storage=FakeStorage(),  # type: ignore[arg-type]
            config=AcquisitionConfig(trigger_timeout_ms=500),
            router=router,
            status_cb=status_cb,
        )
        worker = threading.Thread(
            target=engine.run,
            kwargs={"enable_hardware_trigger": True, "hardware_trigger_slope": "POS"},
        )
        worker.start()
        try:
            self.assertTrue(
                recording_started.wait(timeout=1.0),
                "hardware-trigger worker did not start recording",
            )
            router.publish(TriggerEvent.new(TriggerSource.SOFTWARE))
            self.assertTrue(
                software_ignored.wait(timeout=1.0),
                "worker did not report the ignored software trigger",
            )
        finally:
            engine.stop()
            worker.join(timeout=1)

        self.assertFalse(worker.is_alive())
        self.assertEqual(0, engine.stats.captured)
        self.assertEqual(0, engine.stats.errors)
        self.assertTrue(
            any("software trigger ignored while hardware trigger is enabled" in s for s in statuses)
        )

    def test_max_samples_stops_after_successful_captures(self):
        router = TriggerRouter()
        statuses: list[str] = []
        engine = TriggerAcquisitionEngine(
            instrument=FakeInstrument(),  # type: ignore[arg-type]
            measurement=FakeMeasurement(),  # type: ignore[arg-type]
            storage=FakeStorage(),  # type: ignore[arg-type]
            config=AcquisitionConfig(trigger_timeout_ms=50, max_samples=2),
            router=router,
            status_cb=statuses.append,
        )

        worker = threading.Thread(target=engine.run)
        worker.start()
        router.publish(TriggerEvent.new(TriggerSource.SOFTWARE))
        router.publish(TriggerEvent.new(TriggerSource.SOFTWARE))
        worker.join(timeout=1)

        self.assertFalse(worker.is_alive())
        self.assertEqual(2, engine.stats.captured)
        self.assertTrue(any("max samples reached: 2" in s for s in statuses))

    def test_immediate_mode_captures_without_published_trigger(self):
        statuses: list[str] = []
        engine = TriggerAcquisitionEngine(
            instrument=FakeInstrument(),  # type: ignore[arg-type]
            measurement=FakeMeasurement(),  # type: ignore[arg-type]
            storage=FakeStorage(),  # type: ignore[arg-type]
            config=AcquisitionConfig(trigger_timeout_ms=50, max_samples=1),
            router=TriggerRouter(),
            status_cb=statuses.append,
        )

        worker = threading.Thread(target=engine.run, kwargs={"trigger_mode": "immediate"})
        worker.start()
        worker.join(timeout=1)

        self.assertFalse(worker.is_alive())
        self.assertEqual(1, engine.stats.captured)
        self.assertTrue(any("max samples reached: 1" in s for s in statuses))

    def test_immediate_custom_mode_captures_bounded_batch(self):
        instrument = RecordingInstrument()
        measurement = FakeBufferedMeasurement()
        storage = CapturingStorage()
        statuses: list[str] = []
        engine = TriggerAcquisitionEngine(
            instrument=instrument,  # type: ignore[arg-type]
            measurement=measurement,  # type: ignore[arg-type]
            storage=storage,  # type: ignore[arg-type]
            config=AcquisitionConfig(trigger_timeout_ms=50, trigger_count=1, sample_count=3),
            router=TriggerRouter(),
            status_cb=statuses.append,
        )

        worker = threading.Thread(target=engine.run, kwargs={"trigger_mode": "immediate-custom"})
        worker.start()
        worker.join(timeout=1)

        self.assertFalse(worker.is_alive())
        self.assertEqual(3, engine.stats.captured)
        self.assertEqual(
            ["immediate-custom", "immediate-custom", "immediate-custom"],
            [sample.trigger_source for sample in storage.samples],
        )
        self.assertEqual(
            ["TRIG:SOUR IMM", "TRIG:COUNT 1", "SAMP:COUNT 3", "INIT"],
            instrument.commands,
        )
        self.assertGreaterEqual(instrument.abort_count, 1)
        self.assertEqual([3], measurement.read_counts)
        self.assertTrue(any("immediate custom capture started" in s for s in statuses))
        self.assertTrue(any("captured=3 value=2 A" in s for s in statuses))
        self.assertTrue(any("expected readings reached: 3" in s for s in statuses))

    def test_immediate_custom_mode_respects_buffer_drain_size(self):
        measurement = FakeBufferedMeasurement()
        storage = CapturingStorage()
        engine = TriggerAcquisitionEngine(
            instrument=RecordingInstrument(),  # type: ignore[arg-type]
            measurement=measurement,  # type: ignore[arg-type]
            storage=storage,  # type: ignore[arg-type]
            config=AcquisitionConfig(
                trigger_timeout_ms=50,
                trigger_count=1,
                sample_count=5,
                buffer_drain_size=2,
            ),
            router=TriggerRouter(),
        )

        worker = threading.Thread(target=engine.run, kwargs={"trigger_mode": "immediate-custom"})
        worker.start()
        worker.join(timeout=1)

        self.assertFalse(worker.is_alive())
        self.assertEqual(5, engine.stats.captured)
        self.assertEqual([2, 2, 1], measurement.read_counts)

    def test_buffered_custom_capture_exception_is_fatal_and_stops_worker(self):
        statuses: list[str] = []
        engine = TriggerAcquisitionEngine(
            instrument=RecordingInstrument(),  # type: ignore[arg-type]
            measurement=BufferedReadFailingMeasurement(),  # type: ignore[arg-type]
            storage=FakeStorage(),  # type: ignore[arg-type]
            config=AcquisitionConfig(trigger_timeout_ms=50, trigger_count=1, sample_count=1),
            router=TriggerRouter(),
            status_cb=statuses.append,
        )

        worker = threading.Thread(target=engine.run, kwargs={"trigger_mode": "immediate-custom"})
        worker.start()
        worker.join(timeout=1)

        self.assertFalse(worker.is_alive())
        self.assertEqual(0, engine.stats.captured)
        self.assertEqual(1, engine.stats.errors)
        self.assertIsNotNone(engine.fatal_error)
        self.assertIn("buffered capture failure", engine.fatal_error)
        self.assertTrue(any("buffered capture error count=1" in s for s in statuses))

    def test_software_custom_mode_sends_bus_trigger_and_drains_buffer(self):
        instrument = RecordingInstrument()
        measurement = FakeBufferedMeasurement()
        storage = CapturingStorage()
        statuses: list[str] = []
        router = TriggerRouter()
        engine = TriggerAcquisitionEngine(
            instrument=instrument,  # type: ignore[arg-type]
            measurement=measurement,  # type: ignore[arg-type]
            storage=storage,  # type: ignore[arg-type]
            config=AcquisitionConfig(trigger_timeout_ms=50, trigger_count=2, sample_count=2),
            router=router,
            status_cb=statuses.append,
        )

        worker = threading.Thread(target=engine.run, kwargs={"trigger_mode": "software-custom"})
        worker.start()
        router.publish(TriggerEvent.new(TriggerSource.SOFTWARE))
        router.publish(TriggerEvent.new(TriggerSource.SOFTWARE))
        worker.join(timeout=1)

        self.assertFalse(worker.is_alive())
        self.assertEqual(4, engine.stats.captured)
        self.assertEqual(
            ["software-custom", "software-custom", "software-custom", "software-custom"],
            [sample.trigger_source for sample in storage.samples],
        )
        self.assertEqual(
            ["TRIG:SOUR BUS", "TRIG:COUNT 2", "SAMP:COUNT 2", "INIT", "*TRG", "*TRG"],
            instrument.commands,
        )
        self.assertEqual(2, measurement.bus_triggers_sent)
        self.assertEqual([2, 2], measurement.read_counts)
        self.assertTrue(any("software custom capture armed" in s for s in statuses))
        self.assertTrue(any("software custom trigger sent=2/2" in s for s in statuses))
        self.assertTrue(any("expected readings reached: 4" in s for s in statuses))

    def test_software_custom_points_exception_is_fatal_and_stops_worker(self):
        statuses: list[str] = []
        engine = TriggerAcquisitionEngine(
            instrument=RecordingInstrument(),  # type: ignore[arg-type]
            measurement=BufferedAvailableFailingMeasurement(),  # type: ignore[arg-type]
            storage=FakeStorage(),  # type: ignore[arg-type]
            config=AcquisitionConfig(trigger_timeout_ms=50, trigger_count=1, sample_count=1),
            router=TriggerRouter(),
            status_cb=statuses.append,
        )

        worker = threading.Thread(target=engine.run, kwargs={"trigger_mode": "software-custom"})
        worker.start()
        worker.join(timeout=1)

        self.assertFalse(worker.is_alive())
        self.assertEqual(0, engine.stats.captured)
        self.assertEqual(1, engine.stats.errors)
        self.assertIsNotNone(engine.fatal_error)
        self.assertIn("buffered capture failure", engine.fatal_error)
        self.assertTrue(any("buffered capture error count=1" in s for s in statuses))

    def test_software_custom_waiting_trigger_status_is_emitted_once_while_idle(self):
        statuses: list[str] = []
        engine = TriggerAcquisitionEngine(
            instrument=RecordingInstrument(),  # type: ignore[arg-type]
            measurement=FakeBufferedMeasurement(),  # type: ignore[arg-type]
            storage=FakeStorage(),  # type: ignore[arg-type]
            config=AcquisitionConfig(trigger_timeout_ms=50, trigger_count=1, sample_count=2),
            router=TriggerRouter(),
            status_cb=statuses.append,
        )

        worker = threading.Thread(target=engine.run, kwargs={"trigger_mode": "software-custom"})
        worker.start()
        deadline = time.monotonic() + 1.0
        while "waiting software custom trigger" not in statuses and time.monotonic() < deadline:
            time.sleep(0.01)
        time.sleep(0.15)
        engine.stop()
        worker.join(timeout=1)

        self.assertFalse(worker.is_alive())
        self.assertEqual(1, statuses.count("waiting software custom trigger"))

    def test_soft_stop_event_stops_software_custom_before_trigger(self):
        router = TriggerRouter()
        instrument = RecordingInstrument()
        statuses: list[str] = []
        engine = TriggerAcquisitionEngine(
            instrument=instrument,  # type: ignore[arg-type]
            measurement=FakeBufferedMeasurement(),  # type: ignore[arg-type]
            storage=FakeStorage(),  # type: ignore[arg-type]
            config=AcquisitionConfig(trigger_timeout_ms=50, trigger_count=1, sample_count=2),
            router=router,
            status_cb=statuses.append,
        )

        worker = threading.Thread(target=engine.run, kwargs={"trigger_mode": "software-custom"})
        worker.start()
        router.publish(TriggerEvent.new(TriggerSource.SOFTWARE, {"control": "stop"}))
        worker.join(timeout=1)

        self.assertFalse(worker.is_alive())
        self.assertEqual(0, engine.stats.captured)
        self.assertGreaterEqual(instrument.abort_count, 1)
        self.assertTrue(any("stop request received" in s for s in statuses))

    def test_external_custom_mode_arms_external_sequence_and_drains_buffer(self):
        instrument = RecordingInstrument()
        measurement = FakeBufferedMeasurement()
        storage = CapturingStorage()
        statuses: list[str] = []
        engine = TriggerAcquisitionEngine(
            instrument=instrument,  # type: ignore[arg-type]
            measurement=measurement,  # type: ignore[arg-type]
            storage=storage,  # type: ignore[arg-type]
            config=AcquisitionConfig(
                trigger_timeout_ms=50,
                trigger_count=2,
                sample_count=2,
                hw_trigger_delay_s=0.25,
            ),
            router=TriggerRouter(),
            status_cb=statuses.append,
        )

        worker = threading.Thread(
            target=engine.run,
            kwargs={"trigger_mode": "external-custom", "hardware_trigger_slope": "POS"},
        )
        worker.start()
        worker.join(timeout=1)

        self.assertFalse(worker.is_alive())
        self.assertEqual(4, engine.stats.captured)
        self.assertEqual(
            ["external-custom", "external-custom", "external-custom", "external-custom"],
            [sample.trigger_source for sample in storage.samples],
        )
        self.assertEqual(
            [
                "TRIG:SOUR EXT",
                "TRIG:SLOP POS",
                "TRIG:COUNT 2",
                "SAMP:COUNT 2",
                "TRIG:DEL 0.25",
                "INIT",
            ],
            instrument.commands,
        )
        self.assertEqual([4], measurement.read_counts)
        self.assertTrue(any("external custom capture armed" in s for s in statuses))
        self.assertTrue(any("expected readings reached: 4" in s for s in statuses))

    def test_external_custom_ignores_software_trigger_but_honors_stop(self):
        router = TriggerRouter()
        instrument = RecordingInstrument()
        statuses: list[str] = []
        engine = TriggerAcquisitionEngine(
            instrument=instrument,  # type: ignore[arg-type]
            measurement=WaitingExternalBufferedMeasurement(),  # type: ignore[arg-type]
            storage=FakeStorage(),  # type: ignore[arg-type]
            config=AcquisitionConfig(trigger_timeout_ms=50, trigger_count=1, sample_count=2),
            router=router,
            status_cb=statuses.append,
        )

        worker = threading.Thread(target=engine.run, kwargs={"trigger_mode": "external-custom"})
        worker.start()
        router.publish(TriggerEvent.new(TriggerSource.SOFTWARE))
        deadline = time.monotonic() + 1.0
        while not any("software trigger ignored while external custom is enabled" in s for s in statuses):
            if time.monotonic() >= deadline:
                break
            time.sleep(0.01)
        router.publish(TriggerEvent.new(TriggerSource.SOFTWARE, {"control": "stop"}))
        worker.join(timeout=1)

        self.assertFalse(worker.is_alive())
        self.assertEqual(0, engine.stats.captured)
        self.assertGreaterEqual(instrument.abort_count, 1)
        self.assertTrue(
            any("software trigger ignored while external custom is enabled" in s for s in statuses)
        )
        self.assertTrue(any("stop request received" in s for s in statuses))

    def test_software_custom_infinite_captures_until_stop(self):
        router = TriggerRouter()
        measurement = FakeBufferedMeasurement()
        statuses: list[str] = []
        engine = TriggerAcquisitionEngine(
            instrument=RecordingInstrument(),  # type: ignore[arg-type]
            measurement=measurement,  # type: ignore[arg-type]
            storage=CapturingStorage(),  # type: ignore[arg-type]
            config=AcquisitionConfig(
                trigger_timeout_ms=50,
                trigger_count=None,
                sample_count=2,
                trigger_count_infinite=True,
            ),
            router=router,
            status_cb=statuses.append,
        )

        worker = threading.Thread(target=engine.run, kwargs={"trigger_mode": "software-custom"})
        worker.start()
        router.publish(TriggerEvent.new(TriggerSource.SOFTWARE))
        router.publish(TriggerEvent.new(TriggerSource.SOFTWARE))
        deadline = time.monotonic() + 1.0
        while engine.stats.captured < 4 and time.monotonic() < deadline:
            time.sleep(0.01)
        engine.stop()
        worker.join(timeout=1)

        self.assertFalse(worker.is_alive())
        self.assertEqual(4, engine.stats.captured)
        self.assertTrue(engine.stats.trigger_count_infinite)
        self.assertIsNone(engine.stats.expected_readings)
        self.assertEqual("active", engine.stats.overflow_monitoring)
        self.assertFalse(engine.stats.overflow_detected)
        self.assertEqual("stop_requested", engine.stats.stop_reason)
        self.assertTrue(engine.stats.final_drain_complete)
        self.assertEqual("unknown", engine.stats.data_integrity)
        self.assertTrue(engine.ok)
        self.assertTrue(
            any(
                "trigger_count=infinity" in status and "expected_readings=unbounded" in status
                for status in statuses
            )
        )

    def test_software_custom_infinite_stop_on_overflow_stops_run(self):
        engine = TriggerAcquisitionEngine(
            instrument=RecordingInstrument(),  # type: ignore[arg-type]
            measurement=OverflowAssertingMeasurement(),  # type: ignore[arg-type]
            storage=FakeStorage(),  # type: ignore[arg-type]
            config=AcquisitionConfig(
                trigger_timeout_ms=50,
                trigger_count=None,
                sample_count=2,
                trigger_count_infinite=True,
                stop_on_overflow=True,
            ),
            router=TriggerRouter(),
        )

        worker = threading.Thread(target=engine.run, kwargs={"trigger_mode": "software-custom"})
        worker.start()
        worker.join(timeout=1)

        self.assertFalse(worker.is_alive())
        self.assertEqual("active", engine.stats.overflow_monitoring)
        self.assertTrue(engine.stats.overflow_detected)
        self.assertEqual("overflow_detected", engine.stats.stop_reason)
        self.assertTrue(engine.stats.final_drain_complete)
        self.assertEqual("incomplete", engine.stats.data_integrity)
        self.assertFalse(engine.ok)
        self.assertEqual("overflow_detected", engine.result_reason)

    def test_overflow_detection_without_stop_finishes_but_marks_incomplete(self):
        for stop_after_capture in (False, True):
            with self.subTest(stop_after_capture=stop_after_capture):
                engine = TriggerAcquisitionEngine(
                    instrument=RecordingInstrument(),  # type: ignore[arg-type]
                    measurement=OverflowAssertingMeasurement(),  # type: ignore[arg-type]
                    storage=CapturingStorage(),  # type: ignore[arg-type]
                    config=AcquisitionConfig(
                        trigger_timeout_ms=50,
                        trigger_count=1,
                        sample_count=2,
                        monitor_overflow=True,
                        buffer_drain_size=1,
                    ),
                    router=TriggerRouter(),
                    status_cb=lambda message: engine.stop() if (
                        stop_after_capture and message.startswith("captured=")
                    ) else None,
                )

                worker = threading.Thread(target=engine.run, kwargs={"trigger_mode": "immediate-custom"})
                worker.start()
                worker.join(timeout=1)

                self.assertFalse(worker.is_alive())
                self.assertEqual(2, engine.stats.captured)
                self.assertTrue(engine.stats.overflow_detected)
                self.assertEqual(
                    "stop_requested" if stop_after_capture else "completed", engine.stats.stop_reason
                )
                self.assertTrue(engine.stats.final_drain_complete)
                self.assertEqual("incomplete", engine.stats.data_integrity)
                self.assertFalse(engine.ok)
                self.assertEqual("data_loss", engine.result_reason)

    def test_overflow_monitoring_failure_stops_run_once(self):
        class InvalidStatusInstrument(RecordingInstrument):
            polls = 0

            def query(self, command):
                self.commands.append(command)
                if command == "STAT:QUES:EVEN?":
                    self.polls += 1
                    return "0" if self.polls == 1 else "16384.9"
                if command == "DATA:POINts?":
                    return "0"
                raise AssertionError(command)

        engine = TriggerAcquisitionEngine(
            instrument=InvalidStatusInstrument(),  # type: ignore[arg-type]
            measurement=CurrentMeasurement(),
            storage=FakeStorage(),  # type: ignore[arg-type]
            config=AcquisitionConfig(
                trigger_timeout_ms=50,
                trigger_count=None,
                sample_count=2,
                trigger_count_infinite=True,
            ),
            router=TriggerRouter(),
        )

        worker = threading.Thread(target=engine.run, kwargs={"trigger_mode": "software-custom"})
        worker.start()
        worker.join(timeout=1)

        self.assertFalse(worker.is_alive())
        self.assertEqual(1, engine.stats.errors)
        self.assertEqual("failed", engine.stats.overflow_monitoring)
        self.assertIsNone(engine.stats.overflow_detected)
        self.assertEqual("overflow_monitor_failed", engine.stats.stop_reason)
        self.assertTrue(engine.stats.final_drain_complete)
        self.assertEqual("unknown", engine.stats.data_integrity)
        self.assertFalse(engine.ok)
        self.assertEqual("overflow_monitor_failed", engine.result_reason)
        self.assertIsNone(engine.fatal_error)

    def test_final_drain_reads_buffer_after_stop(self):
        instrument = RecordingInstrument()
        measurement = PostAbortDrainMeasurement(instrument)
        statuses: list[str] = []
        engine = TriggerAcquisitionEngine(
            instrument=instrument,  # type: ignore[arg-type]
            measurement=measurement,  # type: ignore[arg-type]
            storage=CapturingStorage(),  # type: ignore[arg-type]
            config=AcquisitionConfig(
                trigger_timeout_ms=50,
                trigger_count=None,
                sample_count=2,
                trigger_count_infinite=True,
            ),
            router=TriggerRouter(),
            status_cb=statuses.append,
        )

        worker = threading.Thread(target=engine.run, kwargs={"trigger_mode": "software-custom"})
        worker.start()
        deadline = time.monotonic() + 1.0
        while "software custom capture armed" not in statuses and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(0, engine.stats.captured)
        measurement.sample_count = 3

        engine.stop()
        worker.join(timeout=1)

        self.assertFalse(worker.is_alive())
        self.assertEqual(3, engine.stats.captured)
        self.assertEqual([3], measurement.read_counts)
        self.assertEqual("stop_requested", engine.stats.stop_reason)
        self.assertTrue(engine.stats.final_drain_complete)
        self.assertGreaterEqual(instrument.abort_count, 1)

    def test_software_custom_monitoring_waits_for_trigger_ready(self):
        measurement = FakeBufferedMeasurement()
        measurement.trigger_ready = False
        storage = CapturingStorage()
        router = TriggerRouter()
        engine = TriggerAcquisitionEngine(
            instrument=RecordingInstrument(),  # type: ignore[arg-type]
            measurement=measurement,  # type: ignore[arg-type]
            storage=storage,  # type: ignore[arg-type]
            config=AcquisitionConfig(
                trigger_timeout_ms=50,
                trigger_count=1,
                sample_count=1,
                monitor_overflow=True,
            ),
            router=router,
        )

        worker = threading.Thread(target=engine.run, kwargs={"trigger_mode": "software-custom"})
        worker.start()
        router.publish(TriggerEvent.new(TriggerSource.SOFTWARE))
        time.sleep(0.15)
        self.assertEqual(0, measurement.bus_triggers_sent)

        measurement.trigger_ready = True
        worker.join(timeout=2)

        self.assertFalse(worker.is_alive())
        self.assertEqual(1, measurement.bus_triggers_sent)
        self.assertEqual(1, engine.stats.captured)
        self.assertEqual(1, measurement.questionable_clears)
        self.assertGreaterEqual(measurement.standard_event_clears, 1)
        self.assertEqual(1, measurement.opc_requests)
        self.assertFalse(engine.stats.overflow_detected)
        self.assertTrue(engine.ok)

    def test_software_timer_captures_until_max_samples(self):
        storage = CapturingStorage()
        statuses: list[str] = []
        engine = TriggerAcquisitionEngine(
            instrument=FakeInstrument(),  # type: ignore[arg-type]
            measurement=FakeMeasurement(),  # type: ignore[arg-type]
            storage=storage,  # type: ignore[arg-type]
            config=AcquisitionConfig(
                trigger_timeout_ms=50,
                max_samples=2,
                timer_interval_s=0.01,
            ),
            router=TriggerRouter(),
            status_cb=statuses.append,
        )

        worker = threading.Thread(target=engine.run, kwargs={"trigger_mode": "software"})
        worker.start()
        worker.join(timeout=1)

        self.assertFalse(worker.is_alive())
        self.assertEqual(2, engine.stats.captured)
        self.assertEqual(["timer", "timer"], [sample.trigger_source for sample in storage.samples])
        self.assertTrue(any("software timer enabled interval_s=0.01" in s for s in statuses))
        self.assertTrue(any("max samples reached: 2" in s for s in statuses))

    def test_software_trigger_is_ignored_in_timer_mode(self):
        router = TriggerRouter()
        router.publish(TriggerEvent.new(TriggerSource.SOFTWARE))
        storage = CapturingStorage()
        statuses: list[str] = []
        engine = TriggerAcquisitionEngine(
            instrument=FakeInstrument(),  # type: ignore[arg-type]
            measurement=FakeMeasurement(),  # type: ignore[arg-type]
            storage=storage,  # type: ignore[arg-type]
            config=AcquisitionConfig(
                trigger_timeout_ms=50,
                max_samples=1,
                timer_interval_s=0.01,
            ),
            router=router,
            status_cb=statuses.append,
        )

        worker = threading.Thread(target=engine.run, kwargs={"trigger_mode": "software"})
        worker.start()
        worker.join(timeout=1)

        self.assertFalse(worker.is_alive())
        self.assertEqual(1, engine.stats.captured)
        self.assertEqual(["timer"], [sample.trigger_source for sample in storage.samples])
        self.assertTrue(
            any("software trigger ignored while software timer is enabled" in s for s in statuses)
        )

    def test_software_timer_does_not_configure_external_trigger_scpi(self):
        instrument = RecordingInstrument()
        engine = TriggerAcquisitionEngine(
            instrument=instrument,  # type: ignore[arg-type]
            measurement=FakeMeasurement(),  # type: ignore[arg-type]
            storage=FakeStorage(),  # type: ignore[arg-type]
            config=AcquisitionConfig(
                trigger_timeout_ms=50,
                max_samples=1,
                timer_interval_s=0.01,
            ),
            router=TriggerRouter(),
        )

        worker = threading.Thread(target=engine.run, kwargs={"trigger_mode": "software"})
        worker.start()
        worker.join(timeout=1)

        self.assertFalse(worker.is_alive())
        self.assertFalse(any(command.startswith("TRIG:") for command in instrument.commands))

    def test_soft_stop_event_stops_timer_interval_wait(self):
        router = TriggerRouter()
        instrument = FakeInstrument()
        engine = TriggerAcquisitionEngine(
            instrument=instrument,  # type: ignore[arg-type]
            measurement=FakeMeasurement(),  # type: ignore[arg-type]
            storage=FakeStorage(),  # type: ignore[arg-type]
            config=AcquisitionConfig(trigger_timeout_ms=50, timer_interval_s=5.0),
            router=router,
        )

        worker = threading.Thread(target=engine.run, kwargs={"trigger_mode": "software"})
        worker.start()
        deadline = time.monotonic() + 1.0
        while engine.stats.captured == 0 and time.monotonic() < deadline:
            time.sleep(0.01)
        router.publish(TriggerEvent.new(TriggerSource.SOFTWARE, {"control": "stop"}))
        worker.join(timeout=1)

        self.assertFalse(worker.is_alive())
        self.assertEqual(1, engine.stats.captured)
        self.assertGreaterEqual(instrument.abort_count, 1)


if __name__ == "__main__":
    unittest.main()
