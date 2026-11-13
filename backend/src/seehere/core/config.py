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

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    # --- external binaries ---
    ffmpeg_bin: str = "ffmpeg"
    ffprobe_bin: str = "ffprobe"
    tesseract_bin: str = "tesseract"
    ffprobe_timeout_s: float = 30.0
    # Upper bound for one ffmpeg run (audio extraction or frame sampling).
    ffmpeg_timeout_s: float = 900.0

    # --- background jobs (Task 06) ---
    worker_poll_interval_s: float = 1.0
    job_heartbeat_interval_s: float = 5.0
    # A running job whose heartbeat is older than this is treated as abandoned and re-queued.
    job_stale_after_s: float = 60.0
    job_retry_base_s: float = 10.0
    job_retry_max_s: float = 300.0
    retention_sweep_interval_s: float = 60.0
    # Abandoned partial uploads and work directories in media/tmp older than this are removed.
    temp_max_age_hours: float = 6.0

    # --- media preparation (Task 07) ---
    frame_sample_fps: float = 1.0
    frame_max_width: int = 1280

    # --- Vultr Serverless Inference (OpenAI-compatible) ---
    vultr_inference_base_url: str = "https://api.vultrinference.com/v1"
    vultr_inference_api_key: SecretStr | None = None
    vultr_vision_model: str = "qwen3.8-flash-next"
    vultr_tts_model: str = "qwen3-tts-12hz-1.7b"
    vultr_stt_model: str = "whisper-large-v3-turbo"

    # --- optional partner / fallback providers ---
    gemini_api_key: SecretStr | None = None
    smallest_api_key: SecretStr | None = None

    # --- speech-to-text (Task 08): local faster-whisper, the only STT with word timings ---
    local_stt_model: str = "small.en"  # faster-whisper model name or a local model directory
    local_stt_compute_type: str = "int8"
    local_stt_cpu_threads: int = 0  # 0 = let CTranslate2 decide
    local_stt_beam_size: int = 5
    # Model cache directory; None uses the Hugging Face default (~/.cache/huggingface).
    local_stt_model_dir: Path | None = None
    vultr_stt_timeout_s: float = 120.0

    # --- scheduling ---
    extended_pause_budget_pct: float = 8.0
    solver_time_limit_s: float = 2.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
