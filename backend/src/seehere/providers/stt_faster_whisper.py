"""Local speech-to-text with faster-whisper (CTranslate2 Whisper), with word timestamps.

This is SeeHere's primary STT because it returns a start and end time for every word, which is
what speech-safe scheduling needs: the pauses between words are where descriptions can go.
It runs on the CPU of the machine that runs the worker, so it costs nothing per minute.

The model weights are downloaded once from Hugging Face (Systran/faster-whisper-<name>) into the
model cache on first use, then loaded from disk. A model is loaded once per process and reused.

Both capabilities are marked TESTED because `tests/test_stt_faster_whisper.py` runs this adapter
on real recorded speech and checks the words and their timings (see ADR-006).
"""

from __future__ import annotations

import logging
import threading
import wave
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from seehere.providers.base import (
    Capability,
    ProgressCallback,
    ProviderInfo,
    Segment,
    Transcript,
    VerificationState,
    Word,
)

log = logging.getLogger("seehere.stt")

MAX_WORD_CHARS = 100  # transcript_word.text is String(100)

_models: dict[tuple[str, str, int, str | None], Any] = {}
_models_lock = threading.Lock()


class ModelUnavailable(RuntimeError):
    """The model could not be downloaded or loaded (no network on first use, disk full...)."""


def _load_model(name: str, compute_type: str, cpu_threads: int, download_root: str | None) -> Any:
    key = (name, compute_type, cpu_threads, download_root)
    with _models_lock:
        if key not in _models:
            from faster_whisper import WhisperModel  # heavy import, only when STT is used

            log.info("loading faster-whisper model %s (%s)", name, compute_type)
            try:
                _models[key] = WhisperModel(
                    name,
                    device="cpu",
                    compute_type=compute_type,
                    cpu_threads=cpu_threads,
                    download_root=download_root,
                )
            except Exception as exc:  # network, missing files, unsupported compute type
                raise ModelUnavailable(f"could not load speech model {name!r}: {exc}") from exc
        return _models[key]


SAMPLE_RATE = 16_000


def read_pcm16_wav(path: Path) -> npt.NDArray[np.float32]:
    """Read the 16 kHz mono 16-bit WAV that media preparation writes, as floats in [-1, 1).

    The audio is decoded here rather than by faster-whisper's own PyAV decoder, so no second
    general-purpose media decoder parses user-derived files. Anything else is refused.
    """
    with wave.open(str(path), "rb") as f:
        if (f.getnchannels(), f.getsampwidth(), f.getframerate()) != (1, 2, SAMPLE_RATE):
            raise ValueError("expected 16 kHz mono 16-bit PCM audio")
        raw = f.readframes(f.getnframes())
    return np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0


def _ms(seconds: float) -> int:
    return max(0, round(seconds * 1000))


class FasterWhisperSTT:
    def __init__(
        self,
        model: str = "small.en",
        *,
        compute_type: str = "int8",
        cpu_threads: int = 0,
        beam_size: int = 5,
        download_root: Path | None = None,
    ) -> None:
        self.model_name = model
        self.compute_type = compute_type
        self.cpu_threads = cpu_threads
        self.beam_size = beam_size
        self.download_root = str(download_root) if download_root else None

    @property
    def english_only(self) -> bool:
        return self.model_name.endswith(".en")

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            name=f"faster-whisper:{self.model_name}",
            capabilities={
                Capability.TRANSCRIBE_TEXT: VerificationState.TESTED,
                Capability.TRANSCRIBE_WORD_TIMESTAMPS: VerificationState.TESTED,
            },
            notes="Runs locally on CPU. Tested on recorded speech in test_stt_faster_whisper.py.",
        )

    def load(self) -> None:
        """Download (first time only) and load the model. Raises ModelUnavailable."""
        _load_model(self.model_name, self.compute_type, self.cpu_threads, self.download_root)

    def transcribe(
        self,
        audio_path: Path,
        language: str | None = None,
        progress: ProgressCallback | None = None,
    ) -> Transcript:
        if self.english_only and language not in (None, "en"):
            raise ValueError(f"model {self.model_name} only transcribes English")
        model = _load_model(
            self.model_name, self.compute_type, self.cpu_threads, self.download_root
        )
        samples = read_pcm16_wav(audio_path)
        raw_segments, info = model.transcribe(
            samples,
            language="en" if self.english_only else language,
            word_timestamps=True,
            beam_size=self.beam_size,
            # Skip long silences (lectures have many) so Whisper does not invent text in them.
            # Timestamps stay relative to the original audio.
            vad_filter=True,
            # Each window is decoded on its own, which avoids the repetition loops Whisper can
            # fall into on long recordings.
            condition_on_previous_text=False,
        )
        duration_ms = _ms(info.duration)
        segments: list[Segment] = []
        all_words: list[Word] = []
        last_start = 0
        # raw_segments is a generator: decoding happens while we iterate.
        for raw in raw_segments:
            words: list[Word] = []
            for w in raw.words or []:
                text = w.word.strip()[:MAX_WORD_CHARS]
                if not text:
                    continue
                # Keep words in time order and inside the audio, so later stages can rely on it.
                start = min(max(_ms(w.start), last_start), duration_ms)
                end = min(max(_ms(w.end), start), duration_ms)
                last_start = start
                confidence = (
                    None if w.probability is None else min(max(float(w.probability), 0.0), 1.0)
                )
                words.append(Word(text=text, start_ms=start, end_ms=end, confidence=confidence))
            text = raw.text.strip()
            if not text and not words:
                continue
            if words:
                seg_start, seg_end = words[0].start_ms, words[-1].end_ms
            else:
                seg_start = min(max(_ms(raw.start), last_start), duration_ms)
                seg_end = min(max(_ms(raw.end), seg_start), duration_ms)
            segments.append(Segment(text=text, start_ms=seg_start, end_ms=seg_end, words=words))
            all_words.extend(words)
            if progress and duration_ms:
                progress(min(raw.end * 1000 / duration_ms, 1.0))
        return Transcript(
            text=" ".join(s.text for s in segments),
            language=info.language,
            words=all_words,
            segments=segments,
            provider=self.info().name,
            metadata={
                "model": self.model_name,
                "compute_type": self.compute_type,
                "language_probability": round(float(info.language_probability), 4),
                "audio_duration_s": round(float(info.duration), 3),
                "speech_duration_s": round(float(getattr(info, "duration_after_vad", 0.0)), 3),
            },
        )
