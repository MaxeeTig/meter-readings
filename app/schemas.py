from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class MeterType(str, Enum):
    electricity = "electricity"
    hot_water = "hot_water"
    cold_water = "cold_water"


class SourceDate(str, Enum):
    exif = "exif"
    filename = "filename"
    server_time = "server_time"


class OcrDraftResponse(BaseModel):
    draft_id: str
    meter_type: MeterType
    value: float
    unit: str
    confidence: float = Field(ge=0.0, le=1.0)
    captured_at: datetime
    source_date: SourceDate
    filename_original: str
    raw_text: str


class SaveReadingRequest(BaseModel):
    draft_id: str
    meter_type: MeterType
    value: float
    captured_at: datetime


class ReadingRecord(BaseModel):
    id: str
    captured_at: datetime
    saved_at: datetime
    meter_type: MeterType
    value: float
    unit: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_date: SourceDate
    filename_original: str


class ReportPoint(BaseModel):
    date: datetime
    delta: float
    current_value: float


class OcrExtraction(BaseModel):
    meter_type: MeterType
    value: float
    confidence: float = Field(ge=0.0, le=1.0)
    raw_text: str


class OcrError(BaseModel):
    detail: str
    code: Literal["ocr_failed", "invalid_response", "invalid_number"]
