import csv
from datetime import datetime, timezone

from meters_tool_core.models import MeasurementSample
from meters_tool_core.storage import CsvWriter


def test_csv_writer_writes_header_and_row(tmp_path):
    out = tmp_path / "sample.csv"
    writer = CsvWriter(path=out)
    writer.configure_output("full", ())
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


def _sample(at, value, *, buffered=False, trigger="t1"):
    return MeasurementSample(
        timestamp_utc=at,
        measurement_type="current_dc",
        value=value,
        unit="A",
        status="ok",
        resource_id="SIM::34461A",
        trigger_id=trigger,
        trigger_source="immediate-custom" if buffered else "immediate",
        trigger_metadata={"buffered": "true"} if buffered else {},
    )


def test_data_is_default_and_time_columns_are_independent(tmp_path):
    at = datetime(2026, 4, 28, tzinfo=timezone.utc)
    times = iter([1_000_000_000, 2_234_000_000])
    out = tmp_path / "data.csv"
    writer = CsvWriter(out, clock_ns=lambda: next(times))
    writer.configure_output("data", ("elapsed", "delta"))
    writer.open()
    writer.write(_sample(at, 0.123))
    writer.write(_sample(at.replace(second=1), 0.124))
    writer.close()

    with out.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames == [
            "timestamp_utc_plus_8", "value", "unit", "elapsed_s", "delta_t_s"
        ]
        rows = list(reader)
    assert [row["elapsed_s"] for row in rows] == ["0.000", "1.234"]
    assert [row["delta_t_s"] for row in rows] == ["", "1.234"]
    assert [row["value"] for row in rows] == ["0.123", "0.124"]

    only_delta = CsvWriter(tmp_path / "delta.csv", clock_ns=lambda: 123)
    only_delta.configure_output("data", ("delta",))
    only_delta.open()
    only_delta.write(_sample(at, 1.0))
    only_delta.close()
    with (tmp_path / "delta.csv").open(encoding="utf-8", newline="") as fh:
        assert csv.DictReader(fh).fieldnames == [
            "timestamp_utc_plus_8", "value", "unit", "delta_t_s"
        ]


def test_buffered_batch_reuses_one_pc_receipt_time(tmp_path):
    at = datetime(2026, 4, 28, tzinfo=timezone.utc)
    clocks = iter([1_000_000_000, 2_256_000_000])
    out = tmp_path / "buffered.csv"
    writer = CsvWriter(out, clock_ns=lambda: next(clocks))
    writer.configure_output("data", ("elapsed", "delta"))
    writer.open()
    writer.write(_sample(at, 1.0, buffered=True))
    writer.write(_sample(at, 2.0, buffered=True))
    later = at.replace(second=1)
    writer.write(_sample(later, 3.0, buffered=True))
    writer.write(_sample(later, 4.0, buffered=True))
    writer.close()

    with out.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert [row["timestamp_utc_plus_8"] for row in rows] == [
        rows[0]["timestamp_utc_plus_8"], rows[0]["timestamp_utc_plus_8"],
        rows[2]["timestamp_utc_plus_8"], rows[2]["timestamp_utc_plus_8"],
    ]
    assert [row["elapsed_s"] for row in rows] == ["0.000", "0.000", "1.256", "1.256"]
    assert [row["delta_t_s"] for row in rows] == ["", "0.000", "1.256", "0.000"]
