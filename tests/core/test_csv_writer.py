import csv
from datetime import datetime, timezone

from keysight_logger_core.models import MeasurementSample
from keysight_logger_core.storage import CsvWriter


def test_csv_writer_writes_header_and_row(tmp_path):
    out = tmp_path / "sample.csv"
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
    writer.write(
        MeasurementSample(
            timestamp_utc=datetime(2026, 4, 28, 0, 0, 1, tzinfo=timezone.utc),
            measurement_type="voltage_dc_ratio",
            value=1.23,
            unit="ratio",
            status="ok",
            resource_id="TCPIP0::127.0.0.1::inst0::INSTR",
            trigger_id="t2",
            trigger_source="immediate",
            measurement_metadata={
                "signal_voltage_v": 2.46,
                "reference_voltage_v": 2.0,
                "secondary_source": "SENS:DATA",
            },
        )
    )
    writer.close()

    with open(out, "r", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 2
    assert rows[0]["timestamp_utc_plus_8"] == "2026-04-28T08:00:00+08:00"
    assert rows[0]["measurement_type"] == "current_dc"
    assert rows[0]["trigger_source"] == "software"
    assert rows[0]["trigger_metadata"] == '{"batch":"A1","operator":"lab"}'
    assert rows[0]["measurement_metadata"] == "{}"
    assert rows[1]["measurement_type"] == "voltage_dc_ratio"
    assert (
        rows[1]["measurement_metadata"]
        == '{"reference_voltage_v":2.0,"secondary_source":"SENS:DATA","signal_voltage_v":2.46}'
    )
