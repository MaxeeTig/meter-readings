from __future__ import annotations
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main
from app.mosenergosbyt import MosenergosbytState, MosenergosbytStateStore
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


def test_mosenergosbyt_status_and_disconnect_keep_device_token(tmp_path: Path) -> None:
    main.mosenergosbyt_state_store = MosenergosbytStateStore(str(tmp_path / "mosenergosbyt_state.json"))
    main.mosenergosbyt_state_store.save(
        MosenergosbytState(
            session="SESSION",
            id_profile="profile",
            vl_tfa_device_token="device-token",
            authorized_at="2026-03-01T12:00:00+00:00",
        )
    )

    client = TestClient(main.app)

    status_resp = client.get("/api/providers/mosenergosbyt/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["authorized"] is True
    assert status_resp.json()["has_device_token"] is True

    disconnect_resp = client.post("/api/providers/mosenergosbyt/disconnect")
    assert disconnect_resp.status_code == 200
    data = disconnect_resp.json()
    assert data["authorized"] is False
    assert data["has_device_token"] is True


def test_mosenergosbyt_meters_maps_russian_service_names(tmp_path: Path) -> None:
    class FakeMosenergosbytClient:
        async def list_meters(self, *, session: str) -> list[dict]:
            assert session == "SESSION"
            return [
                {
                    "nm_counter": "Г 49065",
                    "nm_service": "ГОРЯЧЕЕ В/С (НОСИТЕЛЬ)",
                    "vl_last_indication": 364,
                    "dt_last_indication": "2026-02-15 00:00:00.0",
                    "id_abonent": 9439925,
                    "id_counter": 35738177,
                    "id_service": 3740,
                },
                {
                    "nm_counter": "Х 24692",
                    "nm_service": "ХОЛОДНОЕ В/С",
                    "vl_last_indication": 522,
                    "dt_last_indication": "2026-02-15 00:00:00.0",
                    "id_abonent": 9439925,
                    "id_counter": 31039410,
                    "id_service": 29508,
                },
            ]

    main.mosenergosbyt_state_store = MosenergosbytStateStore(str(tmp_path / "mosenergosbyt_state.json"))
    main.mosenergosbyt_state_store.save(MosenergosbytState(session="SESSION"))
    main.mosenergosbyt_client = FakeMosenergosbytClient()

    client = TestClient(main.app)
    response = client.get("/api/providers/mosenergosbyt/meters")
    assert response.status_code == 200

    meters = response.json()["meters"]
    assert len(meters) == 2
    assert meters[0]["meter_type"] == "hot_water"
    assert meters[1]["meter_type"] == "cold_water"


def test_mosenergosbyt_submit_requires_auth(tmp_path: Path) -> None:
    main.mosenergosbyt_state_store = MosenergosbytStateStore(str(tmp_path / "mosenergosbyt_state.json"))
    client = TestClient(main.app)

    response = client.post(
        "/api/providers/mosenergosbyt/submit",
        json={
            "id_abonent": 1,
            "id_service": 2,
            "id_counter": 3,
            "value": 100,
        },
    )
    assert response.status_code == 401


def test_mosenergosbyt_submit_rejects_decimals_when_not_allowed(tmp_path: Path) -> None:
    class FakeMosenergosbytClient:
        async def list_meters(self, *, session: str) -> list[dict]:
            return [
                {
                    "id_abonent": 1,
                    "id_service": 2,
                    "id_counter": 3,
                    "id_counter_zn": 1,
                    "pr_state": 1,
                    "nn_ind_receive_start": 1,
                    "nn_ind_receive_end": 31,
                }
            ]

        async def indication_is_float(self, *, session: str, id_service: int | str) -> bool:
            return False

        async def submit_indication(self, **kwargs):
            raise AssertionError("submit_indication should not be called")

    main.mosenergosbyt_state_store = MosenergosbytStateStore(str(tmp_path / "mosenergosbyt_state.json"))
    main.mosenergosbyt_state_store.save(MosenergosbytState(session="SESSION"))
    main.mosenergosbyt_client = FakeMosenergosbytClient()

    client = TestClient(main.app)
    response = client.post(
        "/api/providers/mosenergosbyt/submit",
        json={
            "id_abonent": 1,
            "id_service": 2,
            "id_counter": 3,
            "value": 100.5,
        },
    )
    assert response.status_code == 400


def test_mosenergosbyt_submit_success(tmp_path: Path) -> None:
    class FakeMosenergosbytClient:
        async def list_meters(self, *, session: str) -> list[dict]:
            return [
                {
                    "id_abonent": 1,
                    "id_service": 2,
                    "id_counter": 3,
                    "id_counter_zn": 1,
                    "pr_state": 1,
                    "nn_ind_receive_start": 1,
                    "nn_ind_receive_end": 31,
                }
            ]

        async def indication_is_float(self, *, session: str, id_service: int | str) -> bool:
            return True

        async def submit_indication(self, **kwargs):
            return True, "Показания успешно переданы", 1000

    main.mosenergosbyt_state_store = MosenergosbytStateStore(str(tmp_path / "mosenergosbyt_state.json"))
    main.mosenergosbyt_state_store.save(MosenergosbytState(session="SESSION"))
    main.mosenergosbyt_client = FakeMosenergosbytClient()

    client = TestClient(main.app)
    response = client.post(
        "/api/providers/mosenergosbyt/submit",
        json={
            "id_abonent": 1,
            "id_service": 2,
            "id_counter": 3,
            "value": 100,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["message"] == "Показания успешно переданы"
