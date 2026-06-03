from __future__ import annotations

import csv
import json
from datetime import timedelta, timezone
from pathlib import Path
from typing import Optional

from .models import MeasurementSample

UTC_PLUS_8 = timezone(timedelta(hours=8))


class CsvWriter:
    FIELDNAMES = [
        "timestamp_utc_plus_8",
        "measurement_type",
        "value",
        "unit",
        "trigger_id",
        "trigger_source",
        "trigger_metadata",
        "resource_id",
        "status",
    ]

    def __init__(self, path: Path):
        self._path = path
        self._fh = None
        self._writer: Optional[csv.DictWriter] = None

    def open(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self._path.open("w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._fh, fieldnames=self.FIELDNAMES)
        self._writer.writeheader()
        self._fh.flush()

    def write(self, sample: MeasurementSample) -> None:
        if self._writer is None or self._fh is None:
            raise RuntimeError("CsvWriter is not open")
        timestamp_utc_plus_8 = sample.timestamp_utc.astimezone(UTC_PLUS_8)
        self._writer.writerow(
            {
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
                "resource_id": sample.resource_id,
                "status": sample.status,
            }
        )
        self._fh.flush()

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None
            self._writer = None
