from __future__ import annotations

import threading
import time
import unittest
from datetime import datetime, timezone

from keysight_logger.acquisition import TriggerAcquisitionEngine
from keysight_logger.models import AcquisitionConfig, MeasurementSample, TriggerEvent, TriggerSource
from keysight_logger.trigger import TriggerRouter


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
    def configure(self, instrument, config):  # noqa: ANN001, ARG002
        return

    def read_sample(self, instrument, trigger):  # noqa: ANN001
        return MeasurementSample(
            timestamp_utc=datetime.now(timezone.utc),
            measurement_type="current_dc",
            value=1.23,
            unit="A",
            status="ok",
            resource_id=instrument.resource_id,
            trigger_id=trigger.id,
            trigger_source=trigger.source.value,
        )


class FailingMeasurement(FakeMeasurement):
    def read_sample(self, instrument, trigger):  # noqa: ANN001
        raise AssertionError("software trigger should not be captured")


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


class AcquisitionEngineTests(unittest.TestCase):
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
