"""Application settings, loaded from environment variables (see ../.env.example)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
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
    # Rate limits per client address (Task 32). The player streams video and audio with many
    # range requests, so reads are generous; uploads are the expensive requests.
    rate_limit_enabled: bool = True
    rate_limit_uploads_per_hour: int = Field(default=20, ge=1)
    rate_limit_writes_per_minute: int = Field(default=60, ge=1)
    rate_limit_reads_per_minute: int = Field(default=1200, ge=1)
    trust_proxy_headers: bool = False  # true behind Caddy, which sets X-Forwarded-For

    # --- storage ---
    database_url: str = "postgresql+psycopg://seehere:seehere@localhost:5433/seehere"
    media_dir: Path = Path("./var/media")
    media_retention_hours: int = 24

    # --- upload limits (tuned in Task 05/33 from measured capacity) ---
    max_upload_mb: int = 500
    max_video_duration_s: int = 1800

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

    # --- scene and slide changes (Task 09) ---
    # A new keyframe needs this share of thumbnail pixels to change by more than the delta.
    scene_change_fraction: float = 0.02
    scene_pixel_delta: int = 24

    # --- on-screen text (Task 10) ---
    ocr_language: str = "eng"
    ocr_timeout_s: float = 60.0
    # Lines whose mean word confidence is below this are treated as noise and not stored.
    ocr_min_confidence: float = 0.3

    # --- slide decks (Task 11) ---
    max_deck_mb: int = 50
    # Minimum text similarity (Dice, 0..1) between a page and a keyframe's OCR text to align them.
    slide_align_threshold: float = 0.4

    # --- visual analysis and seen-versus-said (Tasks 12-13) ---
    # "none": units come from OCR only. "vultr" or "gemini": also ask that vision model about
    # each keyframe (each call costs credit or quota).
    vision_provider: Literal["none", "vultr", "gemini"] = "none"
    vultr_vision_timeout_s: float = 90.0
    vision_concurrency: int = Field(default=4, ge=1, le=16)  # keyframes analysed at once
    # Speech this many seconds before/after a unit is on screen counts as describing it.
    coverage_window_pad_s: float = 5.0
    # A spoken pointer is linked to a visual only at or above this confidence (Task 14).
    reference_link_threshold: float = 0.5

    @property
    def max_deck_bytes(self) -> int:
        return self.max_deck_mb * 1024 * 1024

    # --- Vultr Serverless Inference (OpenAI-compatible) ---
    vultr_inference_base_url: str = "https://api.vultrinference.com/v1"
    vultr_inference_api_key: SecretStr | None = None
    vultr_vision_model: str = "qwen3.8-flash-next"
    vultr_tts_model: str = "qwen3-tts-12hz-1.7b"
    vultr_stt_model: str = "whisper-large-v3-turbo"

    # --- optional partner / fallback providers ---
    gemini_api_key: SecretStr | None = None
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    gemini_vision_model: str = "gemini-3.5-flash-lite"
    smallest_api_key: SecretStr | None = None

    # --- speech-to-text (Task 08): local faster-whisper, the only STT with word timings ---
    local_stt_model: str = "small.en"  # faster-whisper model name or a local model directory
    local_stt_compute_type: str = "int8"
    local_stt_cpu_threads: int = 0  # 0 = let CTranslate2 decide
    local_stt_beam_size: int = 5
    # Model cache directory; None uses the Hugging Face default (~/.cache/huggingface).
    local_stt_model_dir: Path | None = None
    vultr_stt_timeout_s: float = 120.0

    # --- scheduling (Tasks 18-19) ---
    window_pad_s: float = 0.15  # kept clear after a word ends and before the next begins
    window_min_s: float = 0.8  # shorter pauses cannot hold a description
    schedule_grace_s: float = 1.0  # a cue may finish this long after its visual leaves
    description_words_per_s: float = 2.6  # speaking-rate estimate until TTS is measured
    extended_pause_budget_pct: float = 8.0
    solver_time_limit_s: float = 2.0

    # --- text-to-speech (Task 22) ---
    # "piper": local voice (default, free). "vultr": Serverless Inference (costs credit).
    tts_provider: Literal["piper", "vultr"] = "piper"
    piper_voice_dir: Path = Path("~/.cache/seehere/piper")
    piper_voice: str = "en_US-ljspeech-medium"
    piper_bin: str = "piper"  # a separate tool (GPL-3.0), run as a process, never imported
    vultr_tts_voice: str = "serena"
    vultr_tts_timeout_s: float = 60.0

    # --- cost estimates (Task 33) ---
    # Unit prices for Vultr Serverless Inference, copied from your Vultr billing page. They are
    # unset by default so no estimate is ever invented: spend is reported as "price not set".
    vultr_price_per_million_tokens_usd: float | None = None
    vultr_price_per_million_tts_chars_usd: float | None = None
    vultr_price_per_stt_minute_usd: float | None = None

    @field_validator("vultr_inference_api_key", "gemini_api_key", "smallest_api_key", mode="before")
    @classmethod
    def _blank_key_is_no_key(cls, v: object) -> object:
        """`KEY=` in .env means "not configured", never an empty bearer token."""
        if isinstance(v, str) and not v.strip():
            return None
        return v.strip() if isinstance(v, str) else v


@lru_cache
def get_settings() -> Settings:
    return Settings()
