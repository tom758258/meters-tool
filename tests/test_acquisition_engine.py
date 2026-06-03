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

    def write(self, command: str) -> None:  # noqa: ARG002
        return


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


if __name__ == "__main__":
    unittest.main()
