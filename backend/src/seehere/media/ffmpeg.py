"""Run ffmpeg safely, with progress, a timeout and cancellation.

- A fixed argv list, never a shell.
- Inputs are opened with `-protocol_whitelist file` and a demuxer whitelist, and paths carry
  the `file:` prefix, so a file can never make ffmpeg open a URL, a playlist or another file.
- `-nostdin`, so ffmpeg never waits for input.
- Progress comes from `-progress pipe:1` (machine-readable key=value lines).
- stderr goes to a temp file (not a pipe), so a chatty ffmpeg can never block on a full pipe;
  its tail is kept for logs only and never shown to users.
"""

from __future__ import annotations

import shutil
import subprocess  # nosec B404 - fixed argv list, no shell
import tempfile
import threading
import time
from collections.abc import Callable, Sequence
from pathlib import Path

INPUT_DEMUXERS = "mov,matroska"


class FFmpegError(Exception):
    """ffmpeg failed or timed out. `detail` is for logs, not for users."""

    def __init__(self, message: str, detail: str = "") -> None:
        super().__init__(message)
        self.detail = detail


class FFmpegCancelled(Exception):
    """The run was stopped because cancellation was requested."""


def input_args(path: Path, demuxers: str = INPUT_DEMUXERS) -> list[str]:
    return ["-protocol_whitelist", "file", "-format_whitelist", demuxers, "-i", f"file:{path}"]


def run_ffmpeg(
    args: Sequence[str],
    *,
    binary: str,
    duration_s: float,
    timeout_s: float,
    on_progress: Callable[[float], None] | None = None,
    cancel: threading.Event | None = None,
) -> None:
    """Run `ffmpeg <args>` to completion. Reports progress as a fraction of `duration_s`.

    Raises FFmpegCancelled if `cancel` is set, FFmpegError on a non-zero exit or timeout.
    `on_progress` is called from this thread, so it may raise to abort the run.
    """
    exe = shutil.which(binary)
    if exe is None:
        raise FFmpegError("ffmpeg is not installed")
    argv = [
        exe,
        "-nostdin",
        "-hide_banner",
        "-v",
        "error",
        "-y",
        "-progress",
        "pipe:1",
        "-nostats",
        "-stats_period",
        "0.5",
        *args,
    ]
    latest = [0.0]

    def read_progress(stream: object) -> None:
        for line in stream:  # type: ignore[attr-defined]
            key, _, value = line.strip().partition("=")
            if key == "out_time_us" and value.isdigit() and duration_s > 0:
                latest[0] = min(int(value) / 1e6 / duration_s, 1.0)

    with tempfile.TemporaryFile() as err:
        proc = subprocess.Popen(  # noqa: S603 - argv list, no shell
            argv, stdout=subprocess.PIPE, stderr=err, stdin=subprocess.DEVNULL, text=True
        )
        reader = threading.Thread(target=read_progress, args=(proc.stdout,), daemon=True)
        reader.start()
        deadline = time.monotonic() + timeout_s
        reported = -1.0
        try:
            while proc.poll() is None:
                if cancel is not None and cancel.is_set():
                    raise FFmpegCancelled
                if time.monotonic() > deadline:
                    raise FFmpegError(f"ffmpeg timed out after {timeout_s:.0f} s")
                if on_progress is not None and latest[0] != reported:
                    reported = latest[0]
                    on_progress(reported)
                time.sleep(0.1)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
            reader.join(timeout=5)
            if proc.stdout is not None:
                proc.stdout.close()
        if proc.returncode != 0:
            err.seek(0)
            tail = err.read()[-2000:].decode("utf-8", "replace")
            raise FFmpegError(f"ffmpeg exited with code {proc.returncode}", tail)
    if on_progress is not None:
        on_progress(1.0)
