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


class MosenergosbytOtpMethod(BaseModel):
    kd_tfa: int
    nm_tfa: str
    pr_active: bool | None = None
    nn_contact: str | None = None


class MosenergosbytStatusResponse(BaseModel):
    authorized: bool
    otp_required: bool
    has_device_token: bool
    authorized_at: datetime | None = None
    otp_methods: list[MosenergosbytOtpMethod] = Field(default_factory=list)
    selected_kd_tfa: int | None = None


class MosenergosbytLoginRequest(BaseModel):
    login: str
    password: str
    vl_device_info: str


class MosenergosbytSendOtpRequest(BaseModel):
    kd_tfa: int | None = None


class MosenergosbytVerifyOtpRequest(BaseModel):
    login: str
    password: str
    vl_device_info: str
    nn_tfa_code: str
    kd_tfa: int


class MosenergosbytMeterRecord(BaseModel):
    meter_type: MeterType | None = None
    nm_counter: str | None = None
    nm_service: str | None = None
    nm_measure_unit: str | None = None
    vl_last_indication: float | None = None
    vl_indication: float | None = None
    dt_last_indication: str | None = None
    dt_indication: str | None = None
    nn_ind_receive_start: int | None = None
    nn_ind_receive_end: int | None = None
    pr_state: int | None = None
    nm_no_access_reason: str | None = None
    id_abonent: int | str | None = None
    id_counter: int | str | None = None
    id_counter_zn: int | str | None = None
    id_service: int | str | None = None


class MosenergosbytMetersResponse(BaseModel):
    meters: list[MosenergosbytMeterRecord]


class MosenergosbytSubmitRequest(BaseModel):
    id_abonent: int | str
    id_service: int | str
    id_counter: int | str
    id_counter_zn: int | str | None = None
    value: float


class MosenergosbytSubmitResponse(BaseModel):
    success: bool
    message: str
    portal_code: int | None = None
