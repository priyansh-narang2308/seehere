"""Provider interfaces.

Every external AI capability sits behind one of these protocols, so a provider can be swapped
(Vultr Serverless Inference, a partner API, or a local model) without touching pipeline code.

Concrete adapters are added in their own tasks (STT: Task 08, vision: Task 12, TTS: Task 22) and
must only claim a capability after it has been tested against the real service. Nothing in this
module calls a network service.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

# Called with the fraction of the audio processed so far (0..1). It may raise to stop the work
# (the job worker raises JobCancelled from it when cancellation was requested).
ProgressCallback = Callable[[float], None]


class Capability(StrEnum):
    TRANSCRIBE_TEXT = "transcribe_text"
    TRANSCRIBE_WORD_TIMESTAMPS = "transcribe_word_timestamps"
    VISION_STRUCTURED = "vision_structured"
    TEXT_STRUCTURED = "text_structured"
    SPEECH_SYNTHESIS = "speech_synthesis"


class VerificationState(StrEnum):
    """How a capability claim was established. Only TESTED may be relied on by the pipeline."""

    DOCUMENTED = "documented"  # read from the provider's catalog/docs, not yet exercised
    TESTED = "tested"  # exercised against the real service by an integration test
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class ProviderInfo:
    name: str
    capabilities: dict[Capability, VerificationState]
    notes: str = ""


@dataclass(frozen=True)
class Word:
    text: str
    start_ms: int
    end_ms: int
    confidence: float | None = None


@dataclass(frozen=True)
class Segment:
    """A stretch of speech as the recognizer grouped it, with its words (if timed)."""

    text: str
    start_ms: int
    end_ms: int
    words: list[Word] = field(default_factory=list)


@dataclass(frozen=True)
class Transcript:
    text: str
    language: str | None
    words: list[Word] = field(default_factory=list)
    segments: list[Segment] = field(default_factory=list)
    provider: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SynthesizedAudio:
    path: Path
    duration_ms: int  # measured from the produced file, never estimated
    provider: str
    voice: str


@runtime_checkable
class SpeechToText(Protocol):
    def info(self) -> ProviderInfo: ...

    def transcribe(
        self,
        audio_path: Path,
        language: str | None = None,
        progress: ProgressCallback | None = None,
    ) -> Transcript: ...


@runtime_checkable
class VisionAnalyzer(Protocol):
    def info(self) -> ProviderInfo: ...

    def analyze(self, image_path: Path, prompt: str, json_schema: dict[str, Any]) -> dict[str, Any]:
        """Return output that has already been validated against ``json_schema``."""
        ...


@runtime_checkable
class TextGenerator(Protocol):
    def info(self) -> ProviderInfo: ...

    def generate_json(self, prompt: str, json_schema: dict[str, Any]) -> dict[str, Any]: ...


@runtime_checkable
class TextToSpeech(Protocol):
    def info(self) -> ProviderInfo: ...

    def synthesize(
        self, text: str, out_path: Path, voice: str | None = None
    ) -> SynthesizedAudio: ...
