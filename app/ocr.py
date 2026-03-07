from __future__ import annotations

import base64
import json
import re
from datetime import datetime
from typing import Any

import httpx

from app.schemas import OcrExtraction


class OcrClient:
    async def extract(
        self,
        image_bytes: bytes,
        filename: str,
        context: dict[str, Any] | None = None,
    ) -> OcrExtraction:
        raise NotImplementedError


class OpenRouterOcrClient(OcrClient):
    def __init__(self, *, api_key: str, model: str, base_url: str, timeout_seconds: int = 45) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def extract(
        self,
        image_bytes: bytes,
        filename: str,
        context: dict[str, Any] | None = None,
    ) -> OcrExtraction:
        if not self.api_key:
            raise RuntimeError("OPENROUTER_API_KEY is missing")

        data_uri = self._to_data_uri(image_bytes, filename)
        prompt = self._prompt(context)

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_uri}},
                    ],
                }
            ],
            "temperature": 0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "meter_reading",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "meter_type": {
                                "type": "string",
                                "enum": ["electricity", "hot_water", "cold_water"],
                            },
                            "value": {"type": "number"},
                            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                            "raw_text": {"type": "string"},
                        },
                        "required": ["meter_type", "value", "confidence", "raw_text"],
                    },
                },
            },
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

        if response.status_code >= 400:
            raise RuntimeError(f"OCR provider error: {response.status_code} {response.text[:300]}")

        data = response.json()
        content = data["choices"][0]["message"]["content"]
        parsed = self._parse_content(content)
        return OcrExtraction.model_validate(parsed)

    def _to_data_uri(self, image_bytes: bytes, filename: str) -> str:
        ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else "jpg"
        mime = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "webp": "image/webp",
            "heic": "image/heic",
        }.get(ext, "image/jpeg")
        encoded = base64.b64encode(image_bytes).decode("ascii")
        return f"data:{mime};base64,{encoded}"

    def _parse_content(self, content: Any) -> dict[str, Any]:
        if isinstance(content, list):
            text = "\n".join(part.get("text", "") for part in content if isinstance(part, dict))
        else:
            text = str(content)

        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?", "", text).strip()
            text = re.sub(r"```$", "", text).strip()

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid OCR JSON response: {exc}") from exc

        if not isinstance(parsed, dict):
            raise RuntimeError("Invalid OCR response type")
        return parsed

    def _prompt(self, context: dict[str, Any] | None) -> str:
        prompt = (
            "Определи показание счетчика на фото и тип счетчика. "
            "Возвращай только JSON по схеме. "
            "Подсказки по типам: "
            "СВУ-15И = hot_water, СВХ-15И = cold_water, Меркурий 202.1 = electricity. "
            "Для water-счетчиков красные цифры после черных обычно дробная часть м3. "
            "Не присоединяй красные дробные цифры к целой части. "
            "Если распознавание похоже на ошибку масштаба (x10/x100/x1000), "
            "используй исторический контекст и верни наиболее правдоподобное значение. "
            "При сомнениях оцени показание на основе предыдущего и среднего расхода. "
            "value должен быть числом, без единиц. "
            "raw_text должен содержать распознанный фрагмент около показания и маркера типа."
        )

        if not context:
            return prompt

        serialized = self._serialize_context(context)
        return f"{prompt}\n\nИсторический контекст:\n{serialized}"

    def _serialize_context(self, context: dict[str, Any]) -> str:
        normalized = dict(context)

        def _to_iso(value: Any) -> Any:
            if isinstance(value, datetime):
                return value.isoformat()
            return value

        if "captured_at" in normalized:
            normalized["captured_at"] = _to_iso(normalized["captured_at"])

        meter_stats = normalized.get("meter_stats")
        if isinstance(meter_stats, dict):
            for meter_type, stats in meter_stats.items():
                if not isinstance(stats, dict):
                    continue
                if "previous_captured_at" in stats:
                    stats["previous_captured_at"] = _to_iso(stats.get("previous_captured_at"))
                meter_stats[meter_type] = stats
            normalized["meter_stats"] = meter_stats

        return json.dumps(normalized, ensure_ascii=False, indent=2)
