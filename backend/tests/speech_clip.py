"""Real recorded speech for speech-to-text tests.

Two sentences are spoken by the system's text-to-speech (macOS `say`, or `espeak-ng` on Linux),
joined by exactly PAUSE_S seconds of digital silence. The test then finds the pause in the audio
itself (by signal energy), which is the independent reference for the word timestamps.
"""

from __future__ import annotations

import shutil
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

FIRST = "Today we look at the bar chart on the left."
SECOND = "Sales doubled between twenty twenty and twenty twenty two."
PAUSE_S = 2.0
RATE = 16_000


@dataclass(frozen=True)
class SpeechClip:
    wav: Path
    duration_s: float
    pause_start_s: float  # measured: the last speech sample before the long pause
    pause_end_s: float  # measured: the first speech sample after it


def _tts(text: str, out: Path) -> None:
    raw = out.with_suffix(".raw.wav")
    if shutil.which("say"):
        aiff = out.with_suffix(".aiff")
        subprocess.run(["say", "-o", str(aiff), text], check=True, timeout=60)
        src = aiff
    elif shutil.which("espeak-ng"):
        subprocess.run(["espeak-ng", "-w", str(raw), text], check=True, timeout=60)
        src = raw
    else:
        pytest.skip("no text-to-speech program (say or espeak-ng) to record test speech")
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(src), "-ac", "1", "-ar", str(RATE)]
        + ["-c:a", "pcm_s16le", str(out)],
        check=True,
        timeout=60,
    )


def _samples(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as f:
        return np.frombuffer(f.readframes(f.getnframes()), dtype="<i2")


def _longest_quiet_run(samples: np.ndarray) -> tuple[float, float]:
    """Start and end (s) of the longest stretch of 10 ms windows with almost no energy."""
    win = RATE // 100
    n = len(samples) // win
    rms = np.sqrt((samples[: n * win].astype(np.float64).reshape(n, win) ** 2).mean(axis=1))
    quiet = rms < 100  # about -50 dBFS
    best, start = (0, 0), None
    for i, q in enumerate([*quiet, False]):
        if q and start is None:
            start = i
        elif not q and start is not None:
            if i - start > best[1] - best[0]:
                best = (start, i)
            start = None
    return best[0] * win / RATE, best[1] * win / RATE


def make_speech_clip(directory: Path) -> SpeechClip:
    a, b = directory / "a.wav", directory / "b.wav"
    _tts(FIRST, a)
    _tts(SECOND, b)
    silence = np.zeros(int(PAUSE_S * RATE), dtype="<i2")
    joined = np.concatenate([_samples(a), silence, _samples(b)])
    out = directory / "speech.wav"
    with wave.open(str(out), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(RATE)
        f.writeframes(joined.tobytes())
    start, end = _longest_quiet_run(joined)
    assert end - start >= PAUSE_S, "the inserted pause should be the longest quiet stretch"
    return SpeechClip(out, len(joined) / RATE, start, end)


def make_speech_video(clip: SpeechClip, out: Path) -> Path:
    """A lecture-like video: a test pattern with the speech clip as its audio track."""
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=10"]
        + ["-i", str(clip.wav), "-t", f"{clip.duration_s:.3f}", "-c:v", "libx264"]
        + ["-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(out)],
        check=True,
        timeout=60,
    )
    return out
