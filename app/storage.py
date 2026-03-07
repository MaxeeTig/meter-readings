from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from app.schemas import MeterType, ReadingRecord


class JsonReadingStore:
    def __init__(self, data_file: str) -> None:
        self.data_file = Path(data_file)
        self._lock = threading.Lock()
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.data_file.exists():
            self._write_raw([])

    def list_readings(
        self,
        *,
        meter_type: MeterType | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[ReadingRecord]:
        rows = [ReadingRecord.model_validate(row) for row in self._read_raw()]

        def normalize(dt: datetime) -> datetime:
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)

        if meter_type is not None:
            rows = [r for r in rows if r.meter_type == meter_type]
        if date_from is not None:
            from_dt = normalize(date_from)
            rows = [r for r in rows if normalize(r.captured_at) >= from_dt]
        if date_to is not None:
            to_dt = normalize(date_to)
            rows = [r for r in rows if normalize(r.captured_at) <= to_dt]

        rows.sort(key=lambda x: normalize(x.captured_at))
        return rows

    def append(self, reading: ReadingRecord) -> None:
        with self._lock:
            rows = self._read_raw()
            rows.append(reading.model_dump(mode="json"))
            self._write_raw(rows)

    def _read_raw(self) -> list[dict]:
        if not self.data_file.exists():
            return []
        try:
            with self.data_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            return []
        if not isinstance(data, list):
            return []
        return [row for row in data if isinstance(row, dict)]

    def _write_raw(self, rows: Iterable[dict]) -> None:
        tmp_path = self.data_file.with_suffix(self.data_file.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(list(rows), f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, self.data_file)
