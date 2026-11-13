"""Application settings, loaded from environment variables (see ../.env.example)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- runtime ---
    app_env: str = Field(default="development", description="development | test | production")
    log_level: str = "INFO"
    api_cors_origins: str = "http://localhost:3000"

    # --- storage ---
    database_url: str = "postgresql+psycopg://seehere:seehere@localhost:5433/seehere"
    media_dir: Path = Path("./var/media")
    media_retention_hours: int = 24

    # --- upload limits (tuned in Task 05/33 from measured capacity) ---
    max_upload_mb: int = 500
    max_video_duration_s: int = 600

    # --- external binaries ---
    ffmpeg_bin: str = "ffmpeg"
    ffprobe_bin: str = "ffprobe"
    tesseract_bin: str = "tesseract"

    # --- Vultr Serverless Inference (OpenAI-compatible) ---
    vultr_inference_base_url: str = "https://api.vultrinference.com/v1"
    vultr_inference_api_key: SecretStr | None = None
    vultr_vision_model: str = "qwen3.8-flash-next"
    vultr_tts_model: str = "qwen3-tts-12hz-1.7b"
    vultr_stt_model: str = "whisper-large-v3-turbo"

    # --- optional partner / fallback providers ---
    gemini_api_key: SecretStr | None = None
    smallest_api_key: SecretStr | None = None
    local_stt_model: str = "small.en"  # faster-whisper model (word timestamps)

    # --- scheduling ---
    extended_pause_budget_pct: float = 8.0
    solver_time_limit_s: float = 2.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
