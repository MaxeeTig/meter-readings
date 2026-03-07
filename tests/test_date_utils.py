from datetime import datetime

from app.date_utils import date_from_filename


def test_parse_filename_date_success() -> None:
    dt = date_from_filename("IMG_20260215_183948.jpg")
    assert dt == datetime(2026, 2, 15, 18, 39, 48)


def test_parse_filename_date_invalid() -> None:
    assert date_from_filename("meter.jpg") is None
