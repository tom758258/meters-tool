from __future__ import annotations

import csv
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Optional

from .constants import UTC_PLUS_8
from .models import MeasurementSample


class CsvWriter:
    FIELDNAMES = [
        "timestamp_utc_plus_8",
        "measurement_type",
        "value",
        "unit",
        "trigger_id",
        "trigger_source",
        "trigger_metadata",
        "measurement_metadata",
        "resource_id",
        "status",
    ]
    DATA_FIELDNAMES = ["timestamp_utc_plus_8", "value", "unit"]
    TIME_FIELDNAMES = {"elapsed": "elapsed_s", "delta": "delta_t_s"}

    def __init__(self, path: Path, clock_ns: Callable[[], int] = time.monotonic_ns):
        self._path = path
        self._fh = None
        self._writer: Optional[csv.DictWriter] = None
        self._clock_ns = clock_ns
        self._csv_format = "data"
        self._time_columns: tuple[str, ...] = ()
        self._first_ns: int | None = None
        self._previous_ns: int | None = None
        self._last_batch_key: tuple[str, object] | None = None

    def configure_output(self, csv_format: str, time_columns: tuple[str, ...]) -> None:
        if self._writer is not None:
            raise RuntimeError("Cannot reconfigure an open CSV writer")
        self._csv_format = csv_format
        self._time_columns = tuple(name for name in ("elapsed", "delta") if name in time_columns)

    def open(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self._path.open("w", newline="", encoding="utf-8")
        base = self.FIELDNAMES if self._csv_format == "full" else self.DATA_FIELDNAMES
        fields = [*base, *(self.TIME_FIELDNAMES[name] for name in self._time_columns)]
        self._writer = csv.DictWriter(self._fh, fieldnames=fields)
        self._first_ns = None
        self._previous_ns = None
        self._last_batch_key = None
        self._writer.writeheader()
        self._fh.flush()

    def write(self, sample: MeasurementSample) -> None:
        if self._writer is None or self._fh is None:
            raise RuntimeError("CsvWriter is not open")
        timestamp_utc_plus_8 = sample.timestamp_utc.astimezone(UTC_PLUS_8)
        row = {
            "timestamp_utc_plus_8": timestamp_utc_plus_8.isoformat(),
            "measurement_type": sample.measurement_type,
            "value": sample.value,
            "unit": sample.unit,
            "trigger_id": sample.trigger_id,
            "trigger_source": sample.trigger_source,
            "trigger_metadata": json.dumps(
                sample.trigger_metadata,
                sort_keys=True,
                separators=(",", ":"),
            ),
            "measurement_metadata": json.dumps(
                sample.measurement_metadata,
                sort_keys=True,
                separators=(",", ":"),
            ),
            "resource_id": sample.resource_id,
            "status": sample.status,
        }
        if self._time_columns:
            # DATA:REMove? returns multiple samples with the same PC fetch time.
            # Keep one writer-arrival timestamp for all readings in that batch.
            batch_key = (
                (sample.trigger_id, sample.timestamp_utc)
                if sample.trigger_metadata.get("buffered") == "true"
                else None
            )
            now_ns = (
                self._previous_ns
                if batch_key is not None and batch_key == self._last_batch_key
                else self._clock_ns()
            )
            if self._first_ns is None:
                self._first_ns = now_ns
            elapsed_s = (now_ns - self._first_ns) / 1_000_000_000
            delta_s = (
                None if self._previous_ns is None
                else (now_ns - self._previous_ns) / 1_000_000_000
            )
            if "elapsed" in self._time_columns:
                row["elapsed_s"] = f"{elapsed_s:.3f}"
            if "delta" in self._time_columns:
                row["delta_t_s"] = "" if delta_s is None else f"{delta_s:.3f}"
            self._previous_ns = now_ns
            self._last_batch_key = batch_key
        self._writer.writerow({name: row[name] for name in self._writer.fieldnames})
        self._fh.flush()

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None
            self._writer = None
