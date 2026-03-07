from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile

from app.config import Settings
from app.date_utils import resolve_captured_at
from app.ocr import OcrClient, OpenRouterOcrClient
from app.reports import build_delta_series
from app.schemas import MeterType, OcrDraftResponse, ReadingRecord, SaveReadingRequest, SourceDate
from app.storage import JsonReadingStore

UNITS = {
    MeterType.electricity: "kWh",
    MeterType.hot_water: "m3",
    MeterType.cold_water: "m3",
}


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


settings = Settings.from_env()
store = JsonReadingStore(settings.data_file)
drafts = DraftStore()
ocr_client: OcrClient = OpenRouterOcrClient(
    api_key=settings.openrouter_api_key,
    model=settings.openrouter_model,
    base_url=settings.openrouter_base_url,
    timeout_seconds=settings.request_timeout_seconds,
)

app = FastAPI(title="Meter Readings Service")


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
        extraction = await ocr_client.extract(content, file.filename)
    except Exception as exc:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(status_code=502, detail=f"Ошибка OCR: {exc}") from exc

    entry = DraftEntry(
        temp_path=temp_path,
        filename_original=file.filename,
        meter_type=extraction.meter_type,
        value=extraction.value,
        confidence=extraction.confidence,
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
