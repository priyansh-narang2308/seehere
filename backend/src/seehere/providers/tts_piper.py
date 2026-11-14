"""Local text-to-speech with Piper, the default and offline voice.

Piper (`piper-tts` 1.3+) is GPL-3.0, so SeeHere never imports it: it is installed as a separate
tool (`make tts-voice`) and run as its own process, like ffmpeg and Tesseract. The text goes in
on stdin, never on the command line.

The default voice is `en_US-ljspeech-medium`, trained on the public-domain LJ Speech dataset.
Durations are measured from the written WAV file, never estimated.
"""

from __future__ import annotations

import shutil
import subprocess
import wave
from pathlib import Path

from seehere.providers.base import Capability, ProviderInfo, SynthesizedAudio, VerificationState


class PiperVoiceMissing(RuntimeError):
    """Piper or the voice model is not installed."""


class PiperError(RuntimeError):
    """Piper ran but produced no usable audio."""


def wav_duration_ms(path: Path) -> int:
    with wave.open(str(path), "rb") as w:
        frames, rate = w.getnframes(), w.getframerate()
    if rate <= 0 or frames <= 0:
        raise ValueError(f"{path.name} contains no audio")
    return round(frames * 1000 / rate)


class PiperTTS:
    def __init__(
        self,
        voice_dir: Path,
        voice: str = "en_US-ljspeech-medium",
        *,
        piper_bin: str = "piper",
        timeout_s: float = 60.0,
    ) -> None:
        self.voice = voice
        self.model_path = (voice_dir.expanduser() / f"{voice}.onnx").resolve()
        self.piper_bin = piper_bin
        self.timeout_s = timeout_s

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            name=f"piper:{self.voice}",
            capabilities={Capability.SPEECH_SYNTHESIS: VerificationState.TESTED},
            notes="Local, offline, separate process. Exercised by the test suite with real audio.",
        )

    def synthesize(self, text: str, out_path: Path, voice: str | None = None) -> SynthesizedAudio:
        if not text.strip():
            raise ValueError("nothing to say")
        exe = shutil.which(self.piper_bin)
        if exe is None or not self.model_path.is_file():
            raise PiperVoiceMissing(
                f"Piper or the voice {self.voice!r} is not installed. Run `make tts-voice`."
            )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = out_path.with_suffix(".part.wav")
        try:
            proc = subprocess.run(  # noqa: S603 - fixed argv, text on stdin
                [exe, "-m", str(self.model_path), "-f", str(tmp)],
                input=" ".join(text.split()),  # one line: piper speaks each input line
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
                check=False,
            )
            if proc.returncode != 0 or not tmp.is_file():
                raise PiperError(f"piper exited with code {proc.returncode}")
            duration = wav_duration_ms(tmp)
            tmp.replace(out_path)
        except subprocess.TimeoutExpired:
            raise PiperError(f"piper took longer than {self.timeout_s:.0f} s") from None
        finally:
            tmp.unlink(missing_ok=True)
        return SynthesizedAudio(out_path, duration, "piper", self.voice)
