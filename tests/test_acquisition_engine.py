from __future__ import annotations

import threading
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
import tempfile

from keysight_logger.acquisition import TriggerAcquisitionEngine
from keysight_logger.models import AcquisitionConfig, MeasurementSample, TriggerEvent, TriggerSource
from keysight_logger.storage import CsvWriter
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


class AcquisitionEngineTests(unittest.TestCase):
    def test_trigger_engine_captures_only_on_trigger(self):
        with tempfile.TemporaryDirectory() as td:
            router = TriggerRouter()
            csv = CsvWriter(Path(td) / "out.csv")
            engine = TriggerAcquisitionEngine(
                instrument=FakeInstrument(),  # type: ignore[arg-type]
                measurement=FakeMeasurement(),  # type: ignore[arg-type]
                storage=csv,
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
        with tempfile.TemporaryDirectory() as td:
            engine = TriggerAcquisitionEngine(
                instrument=instrument,  # type: ignore[arg-type]
                measurement=FakeMeasurement(),  # type: ignore[arg-type]
                storage=CsvWriter(Path(td) / "out.csv"),
                config=AcquisitionConfig(trigger_timeout_ms=50),
                router=router,
            )
            engine.stop()
            self.assertEqual(0, instrument.abort_count)

    def test_control_stop_event_aborts_from_worker_thread(self):
        instrument = FakeInstrument()
        router = TriggerRouter()
        with tempfile.TemporaryDirectory() as td:
            engine = TriggerAcquisitionEngine(
                instrument=instrument,  # type: ignore[arg-type]
                measurement=FakeMeasurement(),  # type: ignore[arg-type]
                storage=CsvWriter(Path(td) / "out.csv"),
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


if __name__ == "__main__":
    unittest.main()
