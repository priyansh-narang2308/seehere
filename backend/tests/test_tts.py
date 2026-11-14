"""Text-to-speech: real Piper audio with measured durations, the Vultr adapter's request and
error handling (mocked; the live call is opt-in because it costs credit), and the job."""

from __future__ import annotations

import io
import json
import os
import shutil
import wave
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from seehere.core.config import Settings
from seehere.providers.base import Capability, VerificationState
from seehere.providers.tts_piper import PiperTTS, wav_duration_ms
from seehere.providers.tts_vultr import VultrTTS, VultrTTSError

VOICE_DIR = Settings().piper_voice_dir
needs_voice = pytest.mark.skipif(
    shutil.which("piper") is None
    or not (VOICE_DIR.expanduser() / f"{Settings().piper_voice}.onnx").is_file(),
    reason="Piper voice not installed (make tts-voice)",
)


def _wav(seconds: float, rate: int = 22050) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\0\0" * int(seconds * rate))
    return buf.getvalue()


@needs_voice
def test_piper_speaks_and_longer_text_takes_longer(tmp_path: Path) -> None:
    tts = PiperTTS(VOICE_DIR)
    assert tts.info().capabilities[Capability.SPEECH_SYNTHESIS] is VerificationState.TESTED
    short = tts.synthesize("Next steps.", tmp_path / "a.wav")
    long = tts.synthesize(
        "On screen: Revenue rose 12.5% to 3.2 million dollars.", tmp_path / "b.wav"
    )
    assert short.duration_ms == wav_duration_ms(short.path) > 300
    assert long.duration_ms > short.duration_ms * 2
    with wave.open(str(long.path), "rb") as w:
        assert w.getnchannels() == 1 and w.getframerate() == 22050
        peak = max(abs(int.from_bytes(w.readframes(1), "little", signed=True)) for _ in range(5000))
    assert peak > 0  # real sound, not silence


def test_missing_piper_or_voice_is_a_clear_error(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="make tts-voice"):
        PiperTTS(tmp_path).synthesize("Hello.", tmp_path / "x.wav")
    with pytest.raises(RuntimeError, match="make tts-voice"):
        PiperTTS(VOICE_DIR, piper_bin="no-such-piper").synthesize("Hi.", tmp_path / "x.wav")


@needs_voice
def test_piper_runs_as_a_separate_process_and_is_never_imported(tmp_path: Path) -> None:
    import sys

    PiperTTS(VOICE_DIR).synthesize("Hello.", tmp_path / "h.wav")
    assert "piper" not in sys.modules  # GPL-3.0: kept out of SeeHere's process


def test_vultr_request_shape_and_measured_duration(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=_wav(1.5))

    tts = VultrTTS(SecretStr("k-123"), transport=httpx.MockTransport(handler))
    assert tts.info().capabilities[Capability.SPEECH_SYNTHESIS] is VerificationState.DOCUMENTED
    out = tts.synthesize("Next steps.", tmp_path / "v.wav")
    assert out.duration_ms == 1500 and out.path.read_bytes()[:4] == b"RIFF"
    req = seen[0]
    assert req.url.path == "/v1/audio/speech"
    assert req.headers["authorization"] == "Bearer k-123"
    assert json.loads(req.content) == {
        "model": "qwen3-tts-12hz-1.7b",
        "input": "Next steps.",
        "voice": "serena",
        "response_format": "wav",
    }


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (httpx.Response(401, text="bad key k-123"), "HTTP 401"),
        (httpx.Response(200, content=b"ID3 not a wav"), "not WAV"),
    ],
)
def test_vultr_errors_never_leak_the_key(
    tmp_path: Path, response: httpx.Response, message: str
) -> None:
    tts = VultrTTS(SecretStr("k-123"), transport=httpx.MockTransport(lambda r: response))
    with pytest.raises(VultrTTSError, match=message) as err:
        tts.synthesize("Hi.", tmp_path / "v.wav")
    assert "k-123" not in str(err.value)
    assert not (tmp_path / "v.wav").exists()


@pytest.mark.skipif(
    os.environ.get("SEEHERE_LIVE_VULTR_TTS") != "1", reason="live call costs credit (opt-in)"
)
def test_live_vultr_tts(tmp_path: Path) -> None:  # pragma: no cover - opt-in
    cfg = Settings()
    if cfg.vultr_inference_api_key is None:
        pytest.fail(
            "VULTR_INFERENCE_API_KEY is empty: subscribe to Serverless Inference and add the key"
        )
    out = VultrTTS(cfg.vultr_inference_api_key, model=cfg.vultr_tts_model).synthesize(
        "On screen: Next steps.", tmp_path / "live.wav"
    )
    assert 500 < out.duration_ms < 6000
