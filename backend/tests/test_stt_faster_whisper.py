"""The local faster-whisper adapter on real recorded speech (no mocks).

This is the integration test that justifies marking word timestamps TESTED (ADR-006). The first
run downloads the model (Systran/faster-whisper-small.en) into the Hugging Face cache.
"""

from __future__ import annotations

import re
import wave
from pathlib import Path

import pytest
from speech_clip import SpeechClip, make_speech_clip

from seehere.core.config import Settings
from seehere.providers.base import Capability, SpeechToText, VerificationState
from seehere.providers.stt_faster_whisper import FasterWhisperSTT, ModelUnavailable, read_pcm16_wav


@pytest.fixture(scope="module")
def clip(tmp_path_factory: pytest.TempPathFactory) -> SpeechClip:
    return make_speech_clip(tmp_path_factory.mktemp("speech"))


@pytest.fixture(scope="module")
def stt() -> FasterWhisperSTT:
    return FasterWhisperSTT(Settings().local_stt_model)


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def test_recognizes_the_spoken_words(stt: FasterWhisperSTT, clip: SpeechClip) -> None:
    t = stt.transcribe(clip.wav)
    words = [_norm(w.text) for w in t.words]
    for expected in ["today", "we", "look", "bar", "chart", "left", "sales", "doubled", "between"]:
        assert expected in words, (expected, t.text)
    assert "bar chart on the left" in t.text.lower()
    assert t.language == "en"
    assert t.provider == "faster-whisper:small.en"
    assert t.metadata["audio_duration_s"] == pytest.approx(clip.duration_s, abs=0.01)
    # segments hold exactly the words, in order
    assert [w for s in t.segments for w in s.words] == t.words


def test_word_timings_are_ordered_and_inside_the_audio(
    stt: FasterWhisperSTT, clip: SpeechClip
) -> None:
    t = stt.transcribe(clip.wav)
    total_ms = round(clip.duration_s * 1000)
    starts = [w.start_ms for w in t.words]
    assert starts == sorted(starts)
    for w in t.words:
        assert 0 <= w.start_ms <= w.end_ms <= total_ms
        assert w.confidence is not None and 0 <= w.confidence <= 1
        assert isinstance(w.confidence, float)
    for s in t.segments:
        assert s.start_ms == s.words[0].start_ms and s.end_ms == s.words[-1].end_ms


def test_the_pause_falls_between_the_right_words(stt: FasterWhisperSTT, clip: SpeechClip) -> None:
    """The gap between "left" and "Sales" must line up with the silence measured in the audio:
    that gap is exactly where a description could be scheduled."""
    t = stt.transcribe(clip.wav)
    words = [_norm(w.text) for w in t.words]
    i = words.index("left")
    assert words[i + 1] == "sales"
    before, after = t.words[i], t.words[i + 1]
    gap_s = (after.start_ms - before.end_ms) / 1000
    assert gap_s >= 1.5, (before, after)
    assert before.end_ms / 1000 == pytest.approx(clip.pause_start_s, abs=0.4)
    assert after.start_ms / 1000 == pytest.approx(clip.pause_end_s, abs=0.4)
    # No word is placed inside the measured silence.
    for w in t.words:
        mid = (w.start_ms + w.end_ms) / 2000
        assert not (clip.pause_start_s + 0.2 < mid < clip.pause_end_s - 0.2), w


def test_progress_is_reported_and_can_stop_the_work(
    stt: FasterWhisperSTT, clip: SpeechClip
) -> None:
    seen: list[float] = []
    stt.transcribe(clip.wav, progress=seen.append)
    assert seen and seen == sorted(seen) and 0 < seen[-1] <= 1

    class Stop(Exception):
        pass

    def stop(_: float) -> None:
        raise Stop

    with pytest.raises(Stop):
        stt.transcribe(clip.wav, progress=stop)


def test_capabilities_are_tested(stt: FasterWhisperSTT) -> None:
    assert isinstance(stt, SpeechToText)
    caps = stt.info().capabilities
    assert caps[Capability.TRANSCRIBE_WORD_TIMESTAMPS] is VerificationState.TESTED
    assert caps[Capability.TRANSCRIBE_TEXT] is VerificationState.TESTED


def test_english_model_refuses_other_languages(stt: FasterWhisperSTT, clip: SpeechClip) -> None:
    with pytest.raises(ValueError, match="only transcribes English"):
        stt.transcribe(clip.wav, language="de")


def test_only_16k_mono_pcm_is_read(tmp_path: Path) -> None:
    stereo = tmp_path / "stereo.wav"
    with wave.open(str(stereo), "wb") as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(44_100)
        f.writeframes(b"\x00\x00" * 200)
    with pytest.raises(ValueError, match="16 kHz mono"):
        read_pcm16_wav(stereo)
    with pytest.raises(wave.Error):
        bad = tmp_path / "bad.wav"
        bad.write_bytes(b"not a wav file at all")
        read_pcm16_wav(bad)


def test_unloadable_model_is_reported(clip: SpeechClip) -> None:
    # An unsupported compute type fails while loading, without any network access.
    with pytest.raises(ModelUnavailable, match="could not load speech model"):
        FasterWhisperSTT("small.en", compute_type="no-such-type").load()
