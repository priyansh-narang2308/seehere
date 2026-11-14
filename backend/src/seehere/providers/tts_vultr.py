"""Text-to-speech through Vultr Serverless Inference (OpenAI-compatible `/audio/speech`).

Status (ADR-006): SPEECH_SYNTHESIS is DOCUMENTED, not TESTED. Each call spends account credit,
so no live request is made without the owner's approval; the opt-in live test is
`SEEHERE_LIVE_VULTR_TTS=1`. Until then Piper is the voice used. WAV output is requested so the
duration can be measured from the file.
"""

from __future__ import annotations

import io
import time
import wave
from pathlib import Path

import httpx
from pydantic import SecretStr

from seehere.core.usage import record_call
from seehere.providers.base import Capability, ProviderInfo, SynthesizedAudio, VerificationState
from seehere.providers.errors import ProviderError
from seehere.providers.tts_piper import wav_duration_ms


class VultrTTSError(ProviderError):
    """The request failed. The message never contains the API key."""


class VultrTTS:
    def __init__(
        self,
        api_key: SecretStr,
        *,
        base_url: str = "https://api.vultrinference.com/v1",
        model: str = "qwen3-tts-12hz-1.7b",
        voice: str = "serena",
        timeout_s: float = 60.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.voice = voice
        self.timeout_s = timeout_s
        self._transport = transport

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            name=f"vultr:{self.model}",
            capabilities={Capability.SPEECH_SYNTHESIS: VerificationState.DOCUMENTED},
            notes="Not yet exercised against the live service (calls cost credit).",
        )

    def synthesize(self, text: str, out_path: Path, voice: str | None = None) -> SynthesizedAudio:
        if not text.strip():
            raise ValueError("nothing to say")
        body = {
            "model": self.model,
            "input": text,
            "voice": voice or self.voice,
            "response_format": "wav",
        }
        started = time.monotonic()
        with httpx.Client(timeout=self.timeout_s, transport=self._transport) as client:
            try:
                r = client.post(
                    f"{self.base_url}/audio/speech",
                    headers={"Authorization": f"Bearer {self._api_key.get_secret_value()}"},
                    json=body,
                )
            except httpx.HTTPError as e:
                record_call("tts", None, started, {"input_chars": len(text)})
                raise VultrTTSError(f"request failed: {type(e).__name__}") from None
        record_call("tts", r.status_code, started, {"input_chars": len(text)})
        if r.status_code != 200:
            raise VultrTTSError(f"HTTP {r.status_code} from text-to-speech", status=r.status_code)
        try:
            with wave.open(io.BytesIO(r.content), "rb") as w:
                w.getframerate()
        except (wave.Error, EOFError):
            raise VultrTTSError("the reply was not WAV audio", retryable=False) from None
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(r.content)
        return SynthesizedAudio(out_path, wav_duration_ms(out_path), "vultr", voice or self.voice)
