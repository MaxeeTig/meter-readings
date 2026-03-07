from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from app.schemas import MeterType, ReadingRecord, ReportPoint


def build_delta_series(readings: list[ReadingRecord]) -> dict[MeterType, list[ReportPoint]]:
    grouped: dict[MeterType, list[ReadingRecord]] = defaultdict(list)
    for reading in readings:
        grouped[reading.meter_type].append(reading)

    result: dict[MeterType, list[ReportPoint]] = {}

    for meter_type, meter_readings in grouped.items():
        meter_readings.sort(key=lambda x: x.captured_at)
        month_totals: dict[datetime, ReportPoint] = {}
        prev_value: float | None = None

        for row in meter_readings:
            if prev_value is None:
                delta = 0.0
            else:
                delta = row.value - prev_value
            month_start = row.captured_at.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            if month_start not in month_totals:
                month_totals[month_start] = ReportPoint(
                    date=month_start,
                    delta=0.0,
                    current_value=row.value,
                )

            bucket = month_totals[month_start]
            bucket.delta = round(bucket.delta + delta, 5)
            # Keep last meter reading in the month for reference.
            bucket.current_value = row.value
            prev_value = row.value

        result[meter_type] = [month_totals[key] for key in sorted(month_totals)]

    return result
