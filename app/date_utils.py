from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from PIL import Image

from app.schemas import SourceDate

FILENAME_PATTERN = re.compile(r"IMG_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})", re.IGNORECASE)


def _parse_exif_datetime(value: str) -> Optional[datetime]:
    # EXIF usually uses format YYYY:MM:DD HH:MM:SS
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    return None


def date_from_exif(path: str) -> Optional[datetime]:
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            # 36867 = DateTimeOriginal, 306 = DateTime
            candidates = [exif.get(36867), exif.get(306)]
            for raw in candidates:
                if isinstance(raw, str):
                    parsed = _parse_exif_datetime(raw)
                    if parsed:
                        return parsed
    except Exception:
        return None
    return None


def date_from_filename(filename: str) -> Optional[datetime]:
    match = FILENAME_PATTERN.search(Path(filename).name)
    if not match:
        return None
    y, m, d, hh, mm, ss = [int(x) for x in match.groups()]
    try:
        return datetime(y, m, d, hh, mm, ss)
    except ValueError:
        return None


def resolve_captured_at(image_path: str, original_filename: str) -> tuple[datetime, SourceDate]:
    exif_dt = date_from_exif(image_path)
    if exif_dt:
        return exif_dt, SourceDate.exif

    file_dt = date_from_filename(original_filename)
    if file_dt:
        return file_dt, SourceDate.filename

    return datetime.now(), SourceDate.server_time
