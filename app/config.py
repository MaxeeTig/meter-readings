from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

@dataclass
class Settings:
    openrouter_api_key: str
    openrouter_model: str
    openrouter_base_url: str
    app_host: str
    app_port: int
    data_file: str
    upload_dir: str
    request_timeout_seconds: int


    @staticmethod
    def from_env() -> "Settings":
        # Allow local .env-based config when running uvicorn directly.
        load_dotenv()
        return Settings(
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY", "").strip(),
            openrouter_model=os.getenv("OPENROUTER_MODEL", "openai/gpt-4.1-mini").strip(),
            openrouter_base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip(),
            app_host=os.getenv("APP_HOST", "0.0.0.0").strip(),
            app_port=int(os.getenv("APP_PORT", "8000")),
            data_file=os.getenv("DATA_FILE", "./data/readings.json").strip(),
            upload_dir=os.getenv("UPLOAD_DIR", "./tmp_uploads").strip(),
            request_timeout_seconds=int(os.getenv("REQUEST_TIMEOUT_SECONDS", "45")),
        )
