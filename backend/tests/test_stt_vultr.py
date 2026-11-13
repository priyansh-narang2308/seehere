"""The Vultr text-only STT adapter.

These tests use a fake HTTP transport, so they only check what the adapter sends and how it
handles answers. Per ADR-006 they do NOT make the capability TESTED: that needs a live call,
which spends account credit and is run only with the owner's approval:

    SEEHERE_LIVE_VULTR_STT=1 VULTR_INFERENCE_API_KEY=... uv run pytest tests/test_stt_vultr.py
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from seehere.core.config import Settings
from seehere.providers.base import Capability, SpeechToText, VerificationState
from seehere.providers.stt_vultr import MAX_UPLOAD_BYTES, VultrSTTError, VultrWhisperSTT

KEY = "test-key-should-never-leak"


@pytest.fixture
def wav(tmp_path: Path) -> Path:
    p = tmp_path / "audio_16k.wav"
    p.write_bytes(b"RIFF....WAVEfmt fake audio")
    return p


def _adapter(handler: httpx.MockTransport) -> VultrWhisperSTT:
    return VultrWhisperSTT(SecretStr(KEY), transport=handler)


def test_sends_an_openai_style_multipart_request(wav: Path) -> None:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"text": "  Today we look at the chart.  "})

    t = _adapter(httpx.MockTransport(handle)).transcribe(wav, language="en")
    assert (t.text, t.language, t.words, t.provider) == (
        "Today we look at the chart.",
        "en",
        [],
        "vultr:whisper-large-v3-turbo",
    )
    [req] = seen
    assert str(req.url) == "https://api.vultrinference.com/v1/audio/transcriptions"
    assert req.headers["authorization"] == f"Bearer {KEY}"
    assert req.headers["content-type"].startswith("multipart/form-data")
    body = req.read()
    for part in [b'name="model"', b"whisper-large-v3-turbo", b'name="response_format"']:
        assert part in body
    assert b'name="file"; filename="audio_16k.wav"' in body and b"fake audio" in body


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(401, json={"error": f"bad key {KEY}"}),
        httpx.Response(200, text="not json"),
        httpx.Response(200, json={"no_text": True}),
    ],
)
def test_errors_never_include_the_key(wav: Path, response: httpx.Response) -> None:
    with pytest.raises(VultrSTTError) as err:
        _adapter(httpx.MockTransport(lambda _: response)).transcribe(wav)
    assert KEY not in str(err.value)


def test_network_errors_are_wrapped(wav: Path) -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"cannot reach {request.headers['authorization']}")

    with pytest.raises(VultrSTTError, match="ConnectError") as err:
        _adapter(httpx.MockTransport(fail)).transcribe(wav)
    assert KEY not in str(err.value)
    assert err.value.__cause__ is None and err.value.__suppress_context__


def test_refuses_audio_over_the_documented_limit(tmp_path: Path) -> None:
    big = tmp_path / "big.wav"
    with big.open("wb") as f:
        f.truncate(MAX_UPLOAD_BYTES + 1)

    def never(_: httpx.Request) -> httpx.Response:
        raise AssertionError("must not send")

    with pytest.raises(VultrSTTError, match="25 MB"):
        _adapter(httpx.MockTransport(never)).transcribe(big)


def test_capabilities_are_documented_only() -> None:
    stt = VultrWhisperSTT(SecretStr(KEY))
    assert isinstance(stt, SpeechToText)
    caps = stt.info().capabilities
    assert caps[Capability.TRANSCRIBE_TEXT] is VerificationState.DOCUMENTED
    assert caps[Capability.TRANSCRIBE_WORD_TIMESTAMPS] is VerificationState.UNAVAILABLE
    assert KEY not in repr(stt.__dict__)


@pytest.mark.skipif(
    os.environ.get("SEEHERE_LIVE_VULTR_STT") != "1",
    reason="live Vultr call spends credit; set SEEHERE_LIVE_VULTR_STT=1 to run it",
)
def test_live_vultr_transcription(tmp_path: Path) -> None:  # pragma: no cover - opt-in
    from speech_clip import make_speech_clip

    settings = Settings()
    if settings.vultr_inference_api_key is None:
        pytest.skip("VULTR_INFERENCE_API_KEY is not set")
    clip = make_speech_clip(tmp_path)
    t = VultrWhisperSTT(
        settings.vultr_inference_api_key,
        base_url=settings.vultr_inference_base_url,
        model=settings.vultr_stt_model,
    ).transcribe(clip.wav, language="en")
    assert "bar chart" in t.text.lower()
