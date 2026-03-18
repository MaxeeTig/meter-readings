from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import httpx


class MosenergosbytError(Exception):
    pass


class MosenergosbytAuthError(MosenergosbytError):
    pass


class MosenergosbytOtpRequired(MosenergosbytError):
    def __init__(
        self,
        *,
        id_profile: str,
        vl_tfa_auth_token: str,
        methods: list[dict[str, Any]],
        nm_result: str,
    ) -> None:
        super().__init__(nm_result or "OTP required")
        self.id_profile = id_profile
        self.vl_tfa_auth_token = vl_tfa_auth_token
        self.methods = methods
        self.nm_result = nm_result


class MosenergosbytSessionExpired(MosenergosbytError):
    pass


@dataclass
class PendingOtpState:
    id_profile: str
    vl_tfa_auth_token: str
    methods: list[dict[str, Any]]
    started_at: str
    selected_kd_tfa: int | None = None


@dataclass
class MosenergosbytState:
    session: str | None = None
    id_profile: str | None = None
    vl_tfa_device_token: str | None = None
    authorized_at: str | None = None
    pending_otp: PendingOtpState | None = None


class MosenergosbytStateStore:
    def __init__(self, state_file: str) -> None:
        self.state_file = Path(state_file)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def load(self) -> MosenergosbytState:
        with self._lock:
            return self._read()

    def save(self, state: MosenergosbytState) -> None:
        with self._lock:
            self._write(state)

    def clear_session(self, keep_device_token: bool = True) -> MosenergosbytState:
        with self._lock:
            state = self._read()
            device_token = state.vl_tfa_device_token if keep_device_token else None
            next_state = MosenergosbytState(vl_tfa_device_token=device_token)
            self._write(next_state)
            return next_state

    def _read(self) -> MosenergosbytState:
        if not self.state_file.exists():
            return MosenergosbytState()
        try:
            raw = json.loads(self.state_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return MosenergosbytState()
        if not isinstance(raw, dict):
            return MosenergosbytState()

        pending_raw = raw.get("pending_otp")
        pending: PendingOtpState | None = None
        if isinstance(pending_raw, dict):
            methods = pending_raw.get("methods")
            if not isinstance(methods, list):
                methods = []
            pending = PendingOtpState(
                id_profile=str(pending_raw.get("id_profile", "")),
                vl_tfa_auth_token=str(pending_raw.get("vl_tfa_auth_token", "")),
                methods=methods,
                started_at=str(pending_raw.get("started_at", "")),
                selected_kd_tfa=pending_raw.get("selected_kd_tfa"),
            )

        return MosenergosbytState(
            session=raw.get("session"),
            id_profile=raw.get("id_profile"),
            vl_tfa_device_token=raw.get("vl_tfa_device_token"),
            authorized_at=raw.get("authorized_at"),
            pending_otp=pending,
        )

    def _write(self, state: MosenergosbytState) -> None:
        payload = asdict(state)
        tmp_path = self.state_file.with_suffix(self.state_file.suffix + ".tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(self.state_file)


def _utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


@dataclass
class MosenergosbytSession:
    session: str
    id_profile: str | None = None
    vl_tfa_device_token: str | None = None
    authorized_at: str = field(default_factory=_utc_now_iso)


class MosenergosbytClient:
    def __init__(self, *, base_url: str, timeout_seconds: int, default_kd_tfa: int) -> None:
        self._base_url = base_url.rstrip("/") + "/"
        self._timeout = timeout_seconds
        self.default_kd_tfa = default_kd_tfa
        self._headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": self._base_url.rstrip("/"),
            "Referer": f"{self._base_url.rstrip('/')}/auth",
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
            ),
        }

    async def login(
        self,
        *,
        login: str,
        password: str,
        device_info: str,
        device_token: str | None = None,
        nn_tfa_code: str | None = None,
        kd_tfa: int | None = None,
    ) -> MosenergosbytSession:
        payload: dict[str, Any] = {
            "login": login,
            "psw": password,
            "vl_device_info": device_info,
        }
        if device_token:
            payload["vl_tfa_device_token"] = device_token
        if nn_tfa_code:
            payload["nn_tfa_code"] = nn_tfa_code
        if kd_tfa:
            payload["kd_tfa"] = str(kd_tfa)

        data = await self._post("gate_lkcomu?action=auth&query=login", payload, referer="/auth")
        row = self._first_row(data)
        kd_result = int(row.get("kd_result", -1))
        nm_result = str(row.get("nm_result", "")).strip()

        if kd_result == 0 and row.get("session"):
            return MosenergosbytSession(
                session=str(row["session"]),
                id_profile=row.get("id_profile"),
                vl_tfa_device_token=row.get("vl_tfa_device_token"),
            )

        if kd_result == 1053:
            raise MosenergosbytOtpRequired(
                id_profile=str(row.get("id_profile", "")),
                vl_tfa_auth_token=str(row.get("vl_tfa_auth_token", "")),
                methods=row.get("method_tfa") if isinstance(row.get("method_tfa"), list) else [],
                nm_result=nm_result,
            )

        raise MosenergosbytAuthError(nm_result or "Login failed")

    async def send_tfa(
        self,
        *,
        id_profile: str,
        kd_tfa: int,
        vl_tfa_auth_token: str,
    ) -> dict[str, Any]:
        payload = {
            "id_profile": id_profile,
            "kd_tfa": str(kd_tfa),
            "vl_tfa_auth_token": vl_tfa_auth_token,
        }
        data = await self._post("gate_lkcomu?action=sql&query=SendTfa", payload, referer="/auth")
        row = self._first_row(data)
        kd_result = int(row.get("kd_result", -1))
        if kd_result != 0:
            raise MosenergosbytAuthError(str(row.get("nm_result") or "Failed to send OTP"))
        return row

    async def init_session(self, *, session: str) -> None:
        await self._post(f"gate_lkcomu?action=sql&query=Init&session={session}", {}, referer="/")

    async def list_accounts(self, *, session: str) -> list[dict[str, Any]]:
        primary = await self._post_sql(query="LSList", session=session)
        if primary:
            return primary
        return await self._post_sql(query="LSListEditable", session=session)

    async def list_meters(self, *, session: str) -> list[dict[str, Any]]:
        accounts = await self.list_accounts(session=session)
        meters: list[dict[str, Any]] = []

        for account in accounts:
            id_abonent = account.get("id_abonent")
            if id_abonent is None:
                id_abonent = self._id_abonent_from_account(account)
            if id_abonent is None:
                continue
            body = {
                "plugin": "smorodinaTransProxy",
                "proxyquery": "AbonentEquipment",
                "vl_provider": json.dumps({"id_abonent": id_abonent}, ensure_ascii=False),
            }
            rows = await self._post_sql(query="smorodinaTransProxy", session=session, payload=body)
            for row in rows:
                merged = dict(row)
                merged["id_abonent"] = id_abonent
                meters.append(merged)

        return meters

    async def indication_is_float(self, *, session: str, id_service: int | str) -> bool:
        payload = {"id_service": str(id_service)}
        data = await self._post(
            f"gate_lkcomu?action=sql&query=IndicationIsFloat&session={session}",
            payload,
            referer=f"/accounts/{id_service}/transfer-indications",
        )
        rows = data.get("data")
        if not isinstance(rows, list) or not rows:
            return True
        row = rows[0] if isinstance(rows[0], dict) else {}
        pr_float = row.get("pr_float")
        return bool(pr_float)

    async def submit_indication(
        self,
        *,
        session: str,
        id_abonent: int | str,
        id_service: int | str,
        id_counter: int | str,
        id_counter_zn: int | str,
        id_source: int,
        value: float,
    ) -> tuple[bool, str, int | None]:
        now = datetime.now(timezone(timedelta(hours=3)))
        dt = now.strftime("%Y-%m-%dT%H:%M:%S") + now.strftime("%z")[:3] + ":" + now.strftime("%z")[3:]
        payload = {
            "dt_indication": dt,
            "id_counter": str(id_counter),
            "id_counter_zn": str(id_counter_zn),
            "id_source": str(id_source),
            "plugin": "propagateMoeInd",
            "pr_skip_anomaly": "0",
            "pr_skip_err": "0",
            "vl_indication": str(value),
            "vl_provider": json.dumps({"id_abonent": id_abonent}, ensure_ascii=False),
        }
        data = await self._post(
            f"gate_lkcomu?action=sql&query=AbonentSaveIndication&session={session}",
            payload,
            referer=f"/accounts/{id_service}/transfer-indications",
        )
        if not data.get("success", False):
            return False, str(data.get("nm_result") or "Unknown error"), None
        rows = data.get("data")
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            return False, "No data in response", None
        row = rows[0]
        kd_result = row.get("kd_result")
        message = str(row.get("nm_result") or "")
        if kd_result == 1000:
            return True, message or "Показания успешно переданы", kd_result
        return False, message or "Failed to submit", kd_result

    async def _post_sql(
        self,
        *,
        query: str,
        session: str,
        payload: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        data = await self._post(
            f"gate_lkcomu?action=sql&query={query}&session={session}",
            payload or {},
            referer="/",
        )
        if isinstance(data.get("data"), list):
            rows = [row for row in data["data"] if isinstance(row, dict)]
        else:
            rows = []

        for row in rows:
            kd_result = row.get("kd_result")
            if kd_result in (None, 0):
                continue
            raise MosenergosbytSessionExpired(str(row.get("nm_result") or "Session expired"))
        return rows

    async def _post(
        self,
        path_and_query: str,
        payload: dict[str, Any],
        *,
        referer: str | None = None,
    ) -> dict[str, Any]:
        url = urljoin(self._base_url, path_and_query)
        headers = dict(self._headers)
        if referer is not None:
            headers["Referer"] = f"{self._base_url.rstrip('/')}{referer}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(url, data=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise MosenergosbytError("Invalid response format")
        return data

    @staticmethod
    def _id_abonent_from_account(account: dict[str, Any]) -> int | str | None:
        vl = account.get("vl_provider")
        if not vl:
            return None
        try:
            parsed = json.loads(vl)
        except (json.JSONDecodeError, TypeError):
            return None
        value = parsed.get("id_abonent") if isinstance(parsed, dict) else None
        return value

    @staticmethod
    def _first_row(data: dict[str, Any]) -> dict[str, Any]:
        rows = data.get("data")
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            raise MosenergosbytError("Unexpected login response")
        return rows[0]
