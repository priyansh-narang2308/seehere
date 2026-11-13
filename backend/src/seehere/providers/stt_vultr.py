"""Optional text-only speech-to-text through Vultr Serverless Inference.

Vultr's transcription models advertise only `json`/`text` output, with no word timestamps, so
this adapter can never drive speech-safe scheduling. It exists as an optional cross-check of the
local transcript's wording.

Status (ADR-006): TRANSCRIBE_TEXT is DOCUMENTED, not TESTED. No live request has been made,
because each call spends account credit and needs the owner's approval. The request follows
the OpenAI-compatible `/audio/transcriptions` multipart shape; that shape is an assumption until
a live test confirms it. The pipeline does not call this adapter.
"""

from __future__ import annotations

from pathlib import Path

import httpx
from pydantic import SecretStr

from seehere.providers.base import (
    Capability,
    ProgressCallback,
    ProviderInfo,
    Transcript,
    VerificationState,
)

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # documented request limit


class VultrSTTError(RuntimeError):
    """The request failed. The message never contains the API key."""


class VultrWhisperSTT:
    def __init__(
        self,
        api_key: SecretStr,
        *,
        base_url: str = "https://api.vultrinference.com/v1",
        model: str = "whisper-large-v3-turbo",
        timeout_s: float = 120.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_s = timeout_s
        self._transport = transport

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            name=f"vultr:{self.model}",
            capabilities={
                Capability.TRANSCRIBE_TEXT: VerificationState.DOCUMENTED,
                Capability.TRANSCRIBE_WORD_TIMESTAMPS: VerificationState.UNAVAILABLE,
            },
            notes="Text only. Not yet exercised against the live service (calls cost credit).",
        )

    def transcribe(
        self,
        audio_path: Path,
        language: str | None = None,
        progress: ProgressCallback | None = None,
    ) -> Transcript:
        size = audio_path.stat().st_size
        if size > MAX_UPLOAD_BYTES:
            raise VultrSTTError(f"audio is {size} bytes; the documented limit is 25 MB")
        data = {"model": self.model, "response_format": "json"}
        if language:
            data["language"] = language
        with (
            audio_path.open("rb") as f,
            httpx.Client(timeout=self.timeout_s, transport=self._transport) as client,
        ):
            try:
                r = client.post(
                    f"{self.base_url}/audio/transcriptions",
                    headers={"Authorization": f"Bearer {self._api_key.get_secret_value()}"},
                    data=data,
                    files={"file": (audio_path.name, f, "audio/wav")},
                )
            except httpx.HTTPError as exc:
                raise VultrSTTError(f"request failed: {type(exc).__name__}") from None
        if r.status_code != 200:
            raise VultrSTTError(f"Vultr returned HTTP {r.status_code}")
        try:
            body = r.json()
            text = str(body["text"]).strip()
        except (ValueError, KeyError, TypeError):
            raise VultrSTTError("unexpected response format") from None
        if progress:
            progress(1.0)
        return Transcript(
            text=text,
            language=body.get("language") or language,
            provider=self.info().name,
            metadata={"model": self.model},
        )
