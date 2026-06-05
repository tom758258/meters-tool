from __future__ import annotations

import threading
import time
import unittest
from datetime import datetime, timezone

from keysight_logger.core.acquisition import TriggerAcquisitionEngine
from keysight_logger.core.models import (
    AcquisitionConfig,
    InstrumentProfile,
    MeasurementSample,
    TriggerEvent,
    TriggerSource,
)
from keysight_logger.core.trigger import TriggerRouter


FAKE_NO_BUFFER_PROFILE = InstrumentProfile(
    vendor="Fake",
    model="NO_BUFFER",
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
    aliases=("SMALL_BUFFER",),
    reading_memory_limit=5,
    supported_measurement_types=("current_dc",),
    supports_buffered_reading_memory=True,
    supports_bus_trigger=True,
    supports_external_trigger=True,
    supports_sample_timer=False,
)


class FakeInstrument:
    resource_id = "FAKE::INSTR"

    def __init__(self) -> None:
        self.abort_count = 0

    def write(self, command: str) -> None:  # noqa: ARG002
        return

    def abort_measurement(self) -> bool:
        self.abort_count += 1
        return True


class RecordingInstrument(FakeInstrument):
    def __init__(self) -> None:
        super().__init__()
        self.commands: list[str] = []

    def write(self, command: str) -> None:
        self.commands.append(command)


class FakeMeasurement:
    def __init__(
        self,
        value: float = 1.23,
        unit: str = "A",
        measurement_type: str = "current_dc",
    ) -> None:
        self.value = value
        self.unit = unit
        self.measurement_type = measurement_type

    def configure(self, instrument, config):  # noqa: ANN001, ARG002
        return

    def read_sample(self, instrument, trigger):  # noqa: ANN001
        return MeasurementSample(
            timestamp_utc=datetime.now(timezone.utc),
            measurement_type=self.measurement_type,
            value=self.value,
            unit=self.unit,
            status="ok",
            resource_id=instrument.resource_id,
            trigger_id=trigger.id,
            trigger_source=trigger.source.value,
        )


class FailingMeasurement(FakeMeasurement):
    def read_sample(self, instrument, trigger):  # noqa: ANN001
        raise AssertionError("software trigger should not be captured")


class CaptureFailingMeasurement(FakeMeasurement):
    def read_sample(self, instrument, trigger):  # noqa: ANN001, ARG002
        raise RuntimeError("read failed")


class FakeBufferedMeasurement(FakeMeasurement):
    def __init__(self) -> None:
        self.sample_count = 0
        self.sample_count_per_trigger = 0
        self.started = False
        self.read_counts: list[int] = []
        self.bus_triggers_sent = 0

    def configure_immediate_custom(self, instrument, config, trigger_count, sample_count):  # noqa: ANN001, ARG002
        self.sample_count = trigger_count * sample_count
        instrument.write("TRIG:SOUR IMM")
        instrument.write(f"TRIG:COUNT {trigger_count}")
        instrument.write(f"SAMP:COUNT {sample_count}")

    def configure_software_custom(self, instrument, config, trigger_count, sample_count):  # noqa: ANN001, ARG002
        self.sample_count = 0
        self.sample_count_per_trigger = sample_count
        instrument.write("TRIG:SOUR BUS")
        instrument.write(f"TRIG:COUNT {trigger_count}")
        instrument.write(f"SAMP:COUNT {sample_count}")

    def configure_external_custom(self, instrument, config, trigger_count, sample_count, slope, delay_s):  # noqa: ANN001, ARG002
        self.sample_count = trigger_count * sample_count
        slope_cmd = "POS" if str(slope).upper() == "POS" else "NEG"
        instrument.write("TRIG:SOUR EXT")
        instrument.write(f"TRIG:SLOP {slope_cmd}")
        instrument.write(f"TRIG:COUNT {trigger_count}")
        instrument.write(f"SAMP:COUNT {sample_count}")
        instrument.write(f"TRIG:DEL {max(0.0, float(delay_s))}")

    def send_bus_trigger(self, instrument):  # noqa: ANN001
        self.bus_triggers_sent += 1
        self.sample_count += self.sample_count_per_trigger
        instrument.write("*TRG")

    def start_buffered_capture(self, instrument):  # noqa: ANN001
        self.started = True
        instrument.write("INIT")

    def buffered_points_available(self, instrument):  # noqa: ANN001, ARG002
        return max(0, self.sample_count)

    def read_buffered_samples(self, instrument, trigger, count, first_sample_index):  # noqa: ANN001, ARG002
        self.read_counts.append(count)
        self.sample_count -= count
        return [
            MeasurementSample(
                timestamp_utc=datetime.now(timezone.utc),
                measurement_type="current_dc",
                value=float(first_sample_index + offset),
                unit="A",
                status="ok",
                resource_id=instrument.resource_id,
                trigger_id=trigger.id,
                trigger_source=trigger.source.value,
                trigger_metadata={
                    "buffer_index": str(first_sample_index + offset),
                    "time_basis": "pc_data_remove_time_not_instrument_sample_time",
                },
            )
            for offset in range(count)
        ]


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


class WaitingExternalBufferedMeasurement(FakeBufferedMeasurement):
    def configure_external_custom(self, instrument, config, trigger_count, sample_count, slope, delay_s):  # noqa: ANN001, ARG002
        self.sample_count = 0
        slope_cmd = "POS" if str(slope).upper() == "POS" else "NEG"
        instrument.write("TRIG:SOUR EXT")
        instrument.write(f"TRIG:SLOP {slope_cmd}")
        instrument.write(f"TRIG:COUNT {trigger_count}")
        instrument.write(f"SAMP:COUNT {sample_count}")
        instrument.write(f"TRIG:DEL {max(0.0, float(delay_s))}")


class BufferedReadFailingMeasurement(FakeBufferedMeasurement):
    def read_buffered_samples(self, instrument, trigger, count, first_sample_index):  # noqa: ANN001, ARG002
        raise RuntimeError("buffer read failed")


class BufferedAvailableFailingMeasurement(FakeBufferedMeasurement):
    def buffered_points_available(self, instrument):  # noqa: ANN001, ARG002
        raise RuntimeError("points query failed")


class FakeStorage:
    def open(self) -> None:
        return

    def close(self) -> None:
        return

    def write(self, sample) -> None:  # noqa: ANN001, ARG002
        return


class CapturingStorage(FakeStorage):
    def __init__(self) -> None:
        self.samples = []

    def write(self, sample) -> None:  # noqa: ANN001
        self.samples.append(sample)


class PermissionDeniedStorage(FakeStorage):
    def open(self) -> None:
        raise PermissionError(13, "Permission denied", "data\\locked.csv")


class AcquisitionEngineTests(unittest.TestCase):
    def test_storage_open_permission_error_sets_fatal_error(self):
        engine = TriggerAcquisitionEngine(
            instrument=FakeInstrument(),  # type: ignore[arg-type]
            measurement=FakeMeasurement(),  # type: ignore[arg-type]
            storage=PermissionDeniedStorage(),  # type: ignore[arg-type]
            config=AcquisitionConfig(trigger_timeout_ms=50),
            router=TriggerRouter(),
        )

        engine.run()

        self.assertEqual(0, engine.stats.captured)
        self.assertEqual(1, engine.stats.errors)
        self.assertIsNotNone(engine.fatal_error)
        self.assertIn("cannot open CSV output file: data\\locked.csv", engine.fatal_error)
        self.assertIn("file may be open in Excel", engine.fatal_error)

    def test_custom_mode_uses_profile_buffer_support(self):
        engine = TriggerAcquisitionEngine(
            instrument=RecordingInstrument(),  # type: ignore[arg-type]
            measurement=FakeBufferedMeasurement(),  # type: ignore[arg-type]
            storage=FakeStorage(),  # type: ignore[arg-type]
            config=AcquisitionConfig(trigger_timeout_ms=50, trigger_count=1, sample_count=1),
            router=TriggerRouter(),
            instrument_profile=FAKE_NO_BUFFER_PROFILE,
        )

        with self.assertRaisesRegex(ValueError, "NO_BUFFER does not support buffered reading memory"):
            engine.run(trigger_mode="immediate-custom")

    def test_custom_mode_uses_profile_memory_limit(self):
        engine = TriggerAcquisitionEngine(
            instrument=RecordingInstrument(),  # type: ignore[arg-type]
            measurement=FakeBufferedMeasurement(),  # type: ignore[arg-type]
            storage=FakeStorage(),  # type: ignore[arg-type]
            config=AcquisitionConfig(trigger_timeout_ms=50, trigger_count=3, sample_count=2),
            router=TriggerRouter(),
            instrument_profile=FAKE_SMALL_BUFFER_PROFILE,
        )

        with self.assertRaisesRegex(ValueError, "expected readings exceed 5 on the SMALL_BUFFER"):
            engine.run(trigger_mode="immediate-custom")

    def test_trigger_engine_captures_only_on_trigger(self):
        router = TriggerRouter()
        engine = TriggerAcquisitionEngine(
            instrument=FakeInstrument(),  # type: ignore[arg-type]
            measurement=FakeMeasurement(),  # type: ignore[arg-type]
            storage=FakeStorage(),  # type: ignore[arg-type]
            config=AcquisitionConfig(trigger_timeout_ms=50),
            router=router,
        )
        worker = threading.Thread(target=engine.run)
        worker.start()
        time.sleep(0.1)
        self.assertEqual(0, engine.stats.captured)
        router.publish(TriggerEvent.new(TriggerSource.SOFTWARE))
        time.sleep(0.1)
        engine.stop()
        worker.join(timeout=1)
        self.assertEqual(1, engine.stats.captured)

    def test_waiting_trigger_status_is_emitted_once_while_idle(self):
        statuses: list[str] = []
        engine = TriggerAcquisitionEngine(
            instrument=FakeInstrument(),  # type: ignore[arg-type]
            measurement=FakeMeasurement(),  # type: ignore[arg-type]
            storage=FakeStorage(),  # type: ignore[arg-type]
            config=AcquisitionConfig(trigger_timeout_ms=50),
            router=TriggerRouter(),
            status_cb=statuses.append,
        )

        worker = threading.Thread(target=engine.run)
        worker.start()
        time.sleep(0.25)
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
        engine = TriggerAcquisitionEngine(
            instrument=instrument,  # type: ignore[arg-type]
            measurement=FailingMeasurement(),  # type: ignore[arg-type]
            storage=FakeStorage(),  # type: ignore[arg-type]
            config=AcquisitionConfig(trigger_timeout_ms=500),
            router=router,
            status_cb=statuses.append,
        )
        worker = threading.Thread(
            target=engine.run,
            kwargs={"enable_hardware_trigger": True, "hardware_trigger_slope": "POS"},
        )
        worker.start()
        time.sleep(0.1)
        router.publish(TriggerEvent.new(TriggerSource.SOFTWARE))
        time.sleep(0.2)
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
