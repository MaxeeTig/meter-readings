from __future__ import annotations
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main
from app.schemas import MeterType, OcrExtraction


class FakeOcr:
    async def extract(
        self,
        image_bytes: bytes,
        filename: str,
        context: dict | None = None,
    ) -> OcrExtraction:
        assert context is not None
        assert "meter_stats" in context
        return OcrExtraction(
            meter_type=MeterType.electricity,
            value=123.45,
            confidence=0.88,
            raw_text="Меркурий 202.1 12345",
        )


def test_ocr_and_save_flow(tmp_path: Path) -> None:
    # isolate state
    main.store = main.JsonReadingStore(str(tmp_path / "readings.json"))
    main.drafts = main.DraftStore()
    main.ocr_client = FakeOcr()
    main.settings.upload_dir = str(tmp_path / "uploads")

    client = TestClient(main.app)

    files = {"file": ("IMG_20260215_183948.jpg", b"fakejpegdata", "image/jpeg")}
    ocr_resp = client.post("/api/ocr", files=files)
    assert ocr_resp.status_code == 200
    ocr_json = ocr_resp.json()
    assert ocr_json["meter_type"] == "electricity"
    assert ocr_json["value"] == 123.45
    assert ocr_json["source_date"] == "filename"

    upload_files = list((tmp_path / "uploads").glob("*"))
    assert len(upload_files) == 1

    save_payload = {
        "draft_id": ocr_json["draft_id"],
        "meter_type": "electricity",
        "value": 124.0,
        "captured_at": "2026-02-15T18:39:48Z",
    }
    save_resp = client.post("/api/readings", json=save_payload)
    assert save_resp.status_code == 200
    save_json = save_resp.json()
    assert save_json["value"] == 124.0
    assert save_json["unit"] == "kWh"

    assert list((tmp_path / "uploads").glob("*")) == []


def test_report_endpoint(tmp_path: Path) -> None:
    main.store = main.JsonReadingStore(str(tmp_path / "readings.json"))
    client = TestClient(main.app)
    response = client.get("/api/reports/line")
    assert response.status_code == 200
    assert response.json() == {}
