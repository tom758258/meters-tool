import csv
import unittest
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from keysight_logger.models import MeasurementSample
from keysight_logger.storage import CsvWriter


class CsvWriterTests(unittest.TestCase):
    def test_csv_writer_writes_header_and_row(self):
        out_dir = Path.cwd() / ".test-output"
        out_dir.mkdir(exist_ok=True)
        out = out_dir / f"sample-{uuid4().hex}.csv"
        try:
            writer = CsvWriter(path=out)
            writer.open()
            writer.write(
                MeasurementSample(
                    timestamp_utc=datetime(2026, 4, 28, tzinfo=timezone.utc),
                    measurement_type="current_dc",
                    value=0.123,
                    unit="A",
                    status="ok",
                    resource_id="TCPIP0::127.0.0.1::inst0::INSTR",
                    trigger_id="t1",
                    trigger_source="software",
                    trigger_metadata={"batch": "A1", "operator": "lab"},
                )
            )
            writer.close()

            with open(out, "r", encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(1, len(rows))
            self.assertEqual("current_dc", rows[0]["measurement_type"])
            self.assertEqual("software", rows[0]["trigger_source"])
            self.assertEqual('{"batch":"A1","operator":"lab"}', rows[0]["trigger_metadata"])
        finally:
            if out.exists():
                out.unlink()
            try:
                out_dir.rmdir()
            except OSError:
                pass


if __name__ == "__main__":
    unittest.main()
