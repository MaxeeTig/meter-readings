from __future__ import annotations

import base64
import json
import re
from typing import Any

import httpx

from app.schemas import OcrExtraction


class OcrClient:
    async def extract(self, image_bytes: bytes, filename: str) -> OcrExtraction:
        raise NotImplementedError


class OpenRouterOcrClient(OcrClient):
    def __init__(self, *, api_key: str, model: str, base_url: str, timeout_seconds: int = 45) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def extract(self, image_bytes: bytes, filename: str) -> OcrExtraction:
        if not self.api_key:
            raise RuntimeError("OPENROUTER_API_KEY is missing")

        data_uri = self._to_data_uri(image_bytes, filename)
        prompt = self._prompt()

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

    def _prompt(self) -> str:
        return (
            "Определи показание счетчика на фото и тип счетчика. "
            "Возвращай только JSON по схеме. "
            "Подсказки по типам: "
            "СВУ-15И = hot_water, СВХ-15И = cold_water, Меркурий 202.1 = electricity. "
            "value должен быть числом, без единиц. "
            "raw_text должен содержать распознанный фрагмент около показания и маркера типа."
        )
