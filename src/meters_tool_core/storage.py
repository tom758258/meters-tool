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
        self._last_batch_key: tuple[str, int] | None = None
        self._next_batch_index: int | None = None
        self._batch_remaining = 0

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
        self._next_batch_index = None
        self._batch_remaining = 0
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
            # Use existing fetch index/size, never an equal wall-clock timestamp.
            metadata = sample.trigger_metadata
            raw_index = metadata.get("buffer_index")
            raw_size = metadata.get("buffer_batch_size")
            valid_batch = (
                metadata.get("buffered") == "true"
                and isinstance(raw_index, str) and raw_index.isascii() and raw_index.isdigit()
                and isinstance(raw_size, str) and raw_size.isascii() and raw_size.isdigit()
            )
            if valid_batch:
                try:
                    index, batch_size = int(raw_index), int(raw_size)
                    valid_batch = batch_size > 0
                except ValueError:
                    valid_batch = False
            same_batch = (
                valid_batch
                and self._batch_remaining > 0
                and self._last_batch_key == (sample.trigger_id, batch_size)
                and self._next_batch_index == index
            )
            now_ns = self._previous_ns if same_batch else self._clock_ns()
            if valid_batch:
                self._last_batch_key = (sample.trigger_id, batch_size)
                self._next_batch_index = index + 1
                self._batch_remaining = self._batch_remaining - 1 if same_batch else batch_size - 1
            else:
                # Missing or invalid metadata: conservatively time each sample.
                self._last_batch_key = None
                self._next_batch_index = None
                self._batch_remaining = 0
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
        self._writer.writerow({name: row[name] for name in self._writer.fieldnames})
        self._fh.flush()

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None
            self._writer = None
