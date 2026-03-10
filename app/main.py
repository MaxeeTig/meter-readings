from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from statistics import mean

from fastapi import FastAPI, File, HTTPException, Query, UploadFile

from app.config import Settings
from app.date_utils import resolve_captured_at
from app.mosenergosbyt import (
    MosenergosbytAuthError,
    MosenergosbytClient,
    MosenergosbytOtpRequired,
    MosenergosbytSessionExpired,
    MosenergosbytState,
    MosenergosbytStateStore,
    PendingOtpState,
)
from app.ocr import OcrClient, OpenRouterOcrClient
from app.reports import build_delta_series
from app.schemas import (
    MeterType,
    MosenergosbytLoginRequest,
    MosenergosbytMeterRecord,
    MosenergosbytMetersResponse,
    MosenergosbytSendOtpRequest,
    MosenergosbytStatusResponse,
    MosenergosbytVerifyOtpRequest,
    OcrDraftResponse,
    ReadingRecord,
    SaveReadingRequest,
    SourceDate,
)
from app.storage import JsonReadingStore

UNITS = {
    MeterType.electricity: "kWh",
    MeterType.hot_water: "m3",
    MeterType.cold_water: "m3",
}


def _normalize_dt(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass
class DraftEntry:
    temp_path: str
    filename_original: str
    meter_type: MeterType
    value: float
    confidence: float
    raw_text: str
    captured_at: datetime
    source_date: SourceDate


class DraftStore:
    def __init__(self) -> None:
        self._drafts: dict[str, DraftEntry] = {}

    def put(self, entry: DraftEntry) -> str:
        draft_id = str(uuid.uuid4())
        self._drafts[draft_id] = entry
        return draft_id

    def get(self, draft_id: str) -> DraftEntry | None:
        return self._drafts.get(draft_id)

    def pop(self, draft_id: str) -> DraftEntry | None:
        return self._drafts.pop(draft_id, None)


def _build_meter_stats(captured_at: datetime) -> dict[str, dict[str, float | str | None]]:
    stats: dict[str, dict[str, float | str | None]] = {}

    for meter_type in MeterType:
        readings = store.list_readings(meter_type=meter_type, date_to=captured_at)
        previous = readings[-1] if readings else None

        daily_rates: list[float] = []
        for prev_row, row in zip(readings, readings[1:]):
            days = (_normalize_dt(row.captured_at) - _normalize_dt(prev_row.captured_at)).total_seconds() / 86400
            delta = row.value - prev_row.value
            if days > 0 and delta >= 0:
                daily_rates.append(delta / days)

        avg_daily = mean(daily_rates) if daily_rates else None
        avg_monthly = avg_daily * 30 if avg_daily is not None else None

        stats[meter_type.value] = {
            "previous_value": previous.value if previous else None,
            "previous_captured_at": previous.captured_at.isoformat() if previous else None,
            "avg_daily_consumption": round(avg_daily, 6) if avg_daily is not None else None,
            "avg_monthly_consumption": round(avg_monthly, 4) if avg_monthly is not None else None,
        }

    return stats


def _apply_value_guardrails(
    *,
    meter_type: MeterType,
    value: float,
    confidence: float,
    captured_at: datetime,
    meter_stats: dict[str, dict[str, float | str | None]],
) -> tuple[float, float]:
    stats = meter_stats.get(meter_type.value) or {}
    previous_value = stats.get("previous_value")
    avg_daily = stats.get("avg_daily_consumption")
    previous_captured_at = stats.get("previous_captured_at")

    if not isinstance(previous_value, (int, float)):
        return value, confidence

    if value < previous_value:
        return value, confidence

    days = 30.0
    if isinstance(previous_captured_at, str):
        try:
            previous_dt = datetime.fromisoformat(previous_captured_at)
            days = max((_normalize_dt(captured_at) - _normalize_dt(previous_dt)).total_seconds() / 86400, 1.0)
        except ValueError:
            days = 30.0

    avg_daily_num = float(avg_daily) if isinstance(avg_daily, (int, float)) else None
    expected_delta = avg_daily_num * days if avg_daily_num is not None else 0.0
    allowed_delta = max(5.0, expected_delta * 4 + 2.0)

    is_water = meter_type in {MeterType.hot_water, MeterType.cold_water}
    if not is_water or (value - previous_value) <= allowed_delta:
        return value, confidence

    # For water meters, OCR often appends 1-3 red fractional digits to integer part.
    candidates = [value / 10, value / 100, value / 1000]
    valid = [candidate for candidate in candidates if candidate >= previous_value]
    if not valid:
        return value, confidence

    target = previous_value + expected_delta
    corrected = min(valid, key=lambda candidate: abs(candidate - target))
    if abs(corrected - target) >= abs(value - target):
        return value, confidence

    return round(corrected, 3), min(confidence, 0.75)


settings = Settings.from_env()
store = JsonReadingStore(settings.data_file)
drafts = DraftStore()
ocr_client: OcrClient = OpenRouterOcrClient(
    api_key=settings.openrouter_api_key,
    model=settings.openrouter_model,
    base_url=settings.openrouter_base_url,
    timeout_seconds=settings.request_timeout_seconds,
)
mosenergosbyt_state_store = MosenergosbytStateStore(settings.mosenergosbyt_state_file)
mosenergosbyt_client = MosenergosbytClient(
    base_url=settings.mosenergosbyt_base_url,
    timeout_seconds=settings.request_timeout_seconds,
    default_kd_tfa=settings.mosenergosbyt_default_kd_tfa,
)

app = FastAPI(title="Meter Readings Service")


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _to_status_response(state: MosenergosbytState) -> MosenergosbytStatusResponse:
    otp_methods = []
    selected_kd_tfa = None
    if state.pending_otp:
        otp_methods = state.pending_otp.methods
        selected_kd_tfa = state.pending_otp.selected_kd_tfa
    return MosenergosbytStatusResponse(
        authorized=bool(state.session),
        otp_required=state.pending_otp is not None,
        has_device_token=bool(state.vl_tfa_device_token),
        authorized_at=_parse_dt(state.authorized_at),
        otp_methods=otp_methods,
        selected_kd_tfa=selected_kd_tfa,
    )


def _map_portal_meter_type(raw: dict) -> MeterType | None:
    name = str(raw.get("nm_counter") or "").upper()
    service = str(raw.get("nm_service") or "").upper()
    text = f"{name} {service}"
    if any(token in text for token in ("ХОЛОД", "ХВС", "ХВ", "COLD")):
        return MeterType.cold_water
    if any(token in text for token in ("ГОРЯЧ", "ГВС", "ГВ", "HOT")):
        return MeterType.hot_water
    if any(token in text for token in ("ЭЛ", "ЭЛЕКТ", "ELECT")):
        return MeterType.electricity
    return None


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _map_meter(raw: dict) -> MosenergosbytMeterRecord:
    return MosenergosbytMeterRecord(
        meter_type=_map_portal_meter_type(raw),
        nm_counter=raw.get("nm_counter"),
        vl_last_indication=_to_float(raw.get("vl_last_indication")),
        dt_last_indication=raw.get("dt_last_indication"),
        id_abonent=raw.get("id_abonent"),
        id_counter=raw.get("id_counter"),
        id_service=raw.get("id_service"),
    )


@app.get("/")
async def index() -> dict[str, str]:
    return {"status": "ok", "message": "API is running. Frontend is served separately."}


@app.post("/api/ocr", response_model=OcrDraftResponse)
async def ocr_upload(file: UploadFile = File(...)) -> OcrDraftResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Файл не выбран")

    ext = Path(file.filename).suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".heic"}:
        raise HTTPException(status_code=400, detail="Неподдерживаемый формат файла")

    os.makedirs(settings.upload_dir, exist_ok=True)
    draft_temp_name = f"{uuid.uuid4()}{ext or '.jpg'}"
    temp_path = str(Path(settings.upload_dir) / draft_temp_name)

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Пустой файл")

    with open(temp_path, "wb") as f:
        f.write(content)

    captured_at, source_date = resolve_captured_at(temp_path, file.filename)

    try:
        meter_stats = _build_meter_stats(captured_at)
        extraction = await ocr_client.extract(
            content,
            file.filename,
            context={
                "captured_at": captured_at,
                "meter_stats": meter_stats,
            },
        )
    except Exception as exc:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(status_code=502, detail=f"Ошибка OCR: {exc}") from exc

    corrected_value, corrected_confidence = _apply_value_guardrails(
        meter_type=extraction.meter_type,
        value=extraction.value,
        confidence=extraction.confidence,
        captured_at=captured_at,
        meter_stats=meter_stats,
    )

    entry = DraftEntry(
        temp_path=temp_path,
        filename_original=file.filename,
        meter_type=extraction.meter_type,
        value=corrected_value,
        confidence=corrected_confidence,
        raw_text=extraction.raw_text,
        captured_at=captured_at,
        source_date=source_date,
    )
    draft_id = drafts.put(entry)

    return OcrDraftResponse(
        draft_id=draft_id,
        meter_type=entry.meter_type,
        value=entry.value,
        unit=UNITS[entry.meter_type],
        confidence=entry.confidence,
        captured_at=entry.captured_at,
        source_date=entry.source_date,
        filename_original=entry.filename_original,
        raw_text=entry.raw_text,
    )


@app.post("/api/readings", response_model=ReadingRecord)
async def save_reading(payload: SaveReadingRequest) -> ReadingRecord:
    draft = drafts.get(payload.draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Черновик не найден")

    record = ReadingRecord(
        id=str(uuid.uuid4()),
        captured_at=payload.captured_at,
        saved_at=datetime.now(),
        meter_type=payload.meter_type,
        value=payload.value,
        unit=UNITS[payload.meter_type],
        confidence=draft.confidence,
        source_date=draft.source_date,
        filename_original=draft.filename_original,
    )

    store.append(record)
    consumed = drafts.pop(payload.draft_id)
    if consumed and os.path.exists(consumed.temp_path):
        os.remove(consumed.temp_path)

    return record


@app.get("/api/readings", response_model=list[ReadingRecord])
async def list_readings(
    meter_type: MeterType | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
) -> list[ReadingRecord]:
    return store.list_readings(meter_type=meter_type, date_from=date_from, date_to=date_to)


@app.get("/api/reports/line")
async def line_report(
    meter_type: MeterType | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
) -> dict:
    readings = store.list_readings(meter_type=meter_type, date_from=date_from, date_to=date_to)
    series = build_delta_series(readings)
    response = {
        key.value: [point.model_dump(mode="json") for point in points] for key, points in series.items()
    }
    return response


@app.get("/api/providers/mosenergosbyt/status", response_model=MosenergosbytStatusResponse)
async def mosenergosbyt_status() -> MosenergosbytStatusResponse:
    state = mosenergosbyt_state_store.load()
    return _to_status_response(state)


@app.post("/api/providers/mosenergosbyt/login", response_model=MosenergosbytStatusResponse)
async def mosenergosbyt_login(payload: MosenergosbytLoginRequest) -> MosenergosbytStatusResponse:
    state = mosenergosbyt_state_store.load()
    try:
        session_data = await mosenergosbyt_client.login(
            login=payload.login,
            password=payload.password,
            device_info=payload.vl_device_info,
            device_token=state.vl_tfa_device_token,
        )
        await mosenergosbyt_client.init_session(session=session_data.session)
    except MosenergosbytOtpRequired as exc:
        next_state = MosenergosbytState(
            session=None,
            id_profile=exc.id_profile or state.id_profile,
            vl_tfa_device_token=state.vl_tfa_device_token,
            authorized_at=None,
            pending_otp=PendingOtpState(
                id_profile=exc.id_profile,
                vl_tfa_auth_token=exc.vl_tfa_auth_token,
                methods=exc.methods,
                started_at=datetime.now(tz=timezone.utc).isoformat(),
                selected_kd_tfa=mosenergosbyt_client.default_kd_tfa,
            ),
        )
        mosenergosbyt_state_store.save(next_state)
        return _to_status_response(next_state)
    except MosenergosbytAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Mosenergosbyt login failed: {exc}") from exc

    next_state = MosenergosbytState(
        session=session_data.session,
        id_profile=session_data.id_profile or state.id_profile,
        vl_tfa_device_token=session_data.vl_tfa_device_token or state.vl_tfa_device_token,
        authorized_at=session_data.authorized_at,
        pending_otp=None,
    )
    mosenergosbyt_state_store.save(next_state)
    return _to_status_response(next_state)


@app.post("/api/providers/mosenergosbyt/otp/send", response_model=MosenergosbytStatusResponse)
async def mosenergosbyt_send_otp(payload: MosenergosbytSendOtpRequest) -> MosenergosbytStatusResponse:
    state = mosenergosbyt_state_store.load()
    pending = state.pending_otp
    if pending is None:
        raise HTTPException(status_code=400, detail="OTP is not required right now")

    kd_tfa = payload.kd_tfa if payload.kd_tfa is not None else pending.selected_kd_tfa
    if kd_tfa is None:
        kd_tfa = mosenergosbyt_client.default_kd_tfa

    try:
        send_result = await mosenergosbyt_client.send_tfa(
            id_profile=pending.id_profile,
            kd_tfa=kd_tfa,
            vl_tfa_auth_token=pending.vl_tfa_auth_token,
        )
    except MosenergosbytAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Mosenergosbyt OTP send failed: {exc}") from exc

    updated_pending = PendingOtpState(
        id_profile=pending.id_profile,
        vl_tfa_auth_token=str(send_result.get("vl_tfa_auth_token") or pending.vl_tfa_auth_token),
        methods=pending.methods,
        started_at=pending.started_at,
        selected_kd_tfa=kd_tfa,
    )
    next_state = MosenergosbytState(
        session=state.session,
        id_profile=state.id_profile,
        vl_tfa_device_token=state.vl_tfa_device_token,
        authorized_at=state.authorized_at,
        pending_otp=updated_pending,
    )
    mosenergosbyt_state_store.save(next_state)
    return _to_status_response(next_state)


@app.post("/api/providers/mosenergosbyt/otp/verify", response_model=MosenergosbytStatusResponse)
async def mosenergosbyt_verify_otp(payload: MosenergosbytVerifyOtpRequest) -> MosenergosbytStatusResponse:
    state = mosenergosbyt_state_store.load()
    pending = state.pending_otp
    if pending is None:
        raise HTTPException(status_code=400, detail="OTP verification is not expected")

    try:
        session_data = await mosenergosbyt_client.login(
            login=payload.login,
            password=payload.password,
            device_info=payload.vl_device_info,
            nn_tfa_code=payload.nn_tfa_code,
            kd_tfa=payload.kd_tfa,
        )
        await mosenergosbyt_client.init_session(session=session_data.session)
    except MosenergosbytAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except MosenergosbytOtpRequired as exc:
        next_state = MosenergosbytState(
            session=None,
            id_profile=exc.id_profile or state.id_profile,
            vl_tfa_device_token=state.vl_tfa_device_token,
            authorized_at=None,
            pending_otp=PendingOtpState(
                id_profile=exc.id_profile,
                vl_tfa_auth_token=exc.vl_tfa_auth_token,
                methods=exc.methods,
                started_at=datetime.now(tz=timezone.utc).isoformat(),
                selected_kd_tfa=payload.kd_tfa,
            ),
        )
        mosenergosbyt_state_store.save(next_state)
        return _to_status_response(next_state)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Mosenergosbyt OTP verify failed: {exc}") from exc

    next_state = MosenergosbytState(
        session=session_data.session,
        id_profile=session_data.id_profile or state.id_profile,
        vl_tfa_device_token=session_data.vl_tfa_device_token or state.vl_tfa_device_token,
        authorized_at=session_data.authorized_at,
        pending_otp=None,
    )
    mosenergosbyt_state_store.save(next_state)
    return _to_status_response(next_state)


@app.post("/api/providers/mosenergosbyt/disconnect", response_model=MosenergosbytStatusResponse)
async def mosenergosbyt_disconnect() -> MosenergosbytStatusResponse:
    next_state = mosenergosbyt_state_store.clear_session(keep_device_token=True)
    return _to_status_response(next_state)


@app.get("/api/providers/mosenergosbyt/meters", response_model=MosenergosbytMetersResponse)
async def mosenergosbyt_meters() -> MosenergosbytMetersResponse:
    state = mosenergosbyt_state_store.load()
    if not state.session:
        raise HTTPException(status_code=401, detail="Portal authorization required")

    try:
        rows = await mosenergosbyt_client.list_meters(session=state.session)
    except MosenergosbytSessionExpired:
        mosenergosbyt_state_store.clear_session(keep_device_token=True)
        raise HTTPException(status_code=401, detail="Portal session expired, please authorize again")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to load portal meters: {exc}") from exc

    meters = [_map_meter(row) for row in rows]
    return MosenergosbytMetersResponse(meters=meters)
