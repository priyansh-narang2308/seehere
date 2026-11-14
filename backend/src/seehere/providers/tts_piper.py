"""Local text-to-speech with Piper (MIT), the default and offline fallback voice.

The default voice is `en_US-ljspeech-medium`, trained on the public-domain LJ Speech dataset.
Voices are downloaded once (`make tts-voice`) into a cache outside the repository. Durations
are measured from the written WAV file, never estimated.
"""

from __future__ import annotations

import threading
import wave
from pathlib import Path
from typing import Any

from seehere.providers.base import Capability, ProviderInfo, SynthesizedAudio, VerificationState


class PiperVoiceMissing(RuntimeError):
    """The voice model file is not installed."""


def wav_duration_ms(path: Path) -> int:
    with wave.open(str(path), "rb") as w:
        frames, rate = w.getnframes(), w.getframerate()
    if rate <= 0 or frames <= 0:
        raise ValueError(f"{path.name} contains no audio")
    return round(frames * 1000 / rate)


class PiperTTS:
    _lock = threading.Lock()
    _voices: dict[Path, Any] = {}

    def __init__(self, voice_dir: Path, voice: str = "en_US-ljspeech-medium") -> None:
        self.voice = voice
        self.model_path = (voice_dir.expanduser() / f"{voice}.onnx").resolve()

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            name=f"piper:{self.voice}",
            capabilities={Capability.SPEECH_SYNTHESIS: VerificationState.TESTED},
            notes="Local, offline. Exercised by the test suite with real audio.",
        )

    def _load(self) -> Any:
        if not self.model_path.is_file():
            raise PiperVoiceMissing(
                f"Piper voice {self.voice!r} is not installed. Run `make tts-voice`."
            )
        from piper import PiperVoice  # heavy import (onnxruntime), only when speaking

        with self._lock:
            if self.model_path not in self._voices:
                self._voices[self.model_path] = PiperVoice.load(str(self.model_path))
            return self._voices[self.model_path]

    def synthesize(self, text: str, out_path: Path, voice: str | None = None) -> SynthesizedAudio:
        if not text.strip():
            raise ValueError("nothing to say")
        engine = self._load()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(out_path), "wb") as w:
            engine.synthesize_wav(text, w)
        return SynthesizedAudio(out_path, wav_duration_ms(out_path), "piper", self.voice)
