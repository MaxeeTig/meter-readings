from datetime import datetime

from app.reports import build_delta_series
from app.schemas import MeterType, ReadingRecord, SourceDate


def test_build_delta_series() -> None:
    rows = [
        ReadingRecord(
            id="1",
            captured_at=datetime(2026, 2, 1, 10, 0, 0),
            saved_at=datetime(2026, 2, 1, 10, 0, 1),
            meter_type=MeterType.cold_water,
            value=10.0,
            unit="m3",
            confidence=0.9,
            source_date=SourceDate.filename,
            filename_original="IMG_20260201_100000.jpg",
        ),
        ReadingRecord(
            id="2",
            captured_at=datetime(2026, 2, 2, 10, 0, 0),
            saved_at=datetime(2026, 2, 2, 10, 0, 1),
            meter_type=MeterType.cold_water,
            value=12.5,
            unit="m3",
            confidence=0.9,
            source_date=SourceDate.filename,
            filename_original="IMG_20260202_100000.jpg",
        ),
        ReadingRecord(
            id="3",
            captured_at=datetime(2026, 2, 15, 10, 0, 0),
            saved_at=datetime(2026, 2, 15, 10, 0, 1),
            meter_type=MeterType.cold_water,
            value=13.0,
            unit="m3",
            confidence=0.9,
            source_date=SourceDate.filename,
            filename_original="IMG_20260215_100000.jpg",
        ),
        ReadingRecord(
            id="4",
            captured_at=datetime(2026, 3, 2, 10, 0, 0),
            saved_at=datetime(2026, 3, 2, 10, 0, 1),
            meter_type=MeterType.cold_water,
            value=15.0,
            unit="m3",
            confidence=0.9,
            source_date=SourceDate.filename,
            filename_original="IMG_20260302_100000.jpg",
        ),
    ]

    series = build_delta_series(rows)
    points = series[MeterType.cold_water]
    assert len(points) == 2
    assert points[0].date == datetime(2026, 2, 1, 0, 0, 0)
    assert points[0].delta == 3.0
    assert points[1].date == datetime(2026, 3, 1, 0, 0, 0)
    assert points[1].delta == 2.0
