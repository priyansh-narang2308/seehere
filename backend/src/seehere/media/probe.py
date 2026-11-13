"""Identify uploads by their content with ffprobe. File extensions and client MIME types are
never trusted.

ffprobe runs with:
- `-protocol_whitelist file`: it may only read local files (no http, tcp, etc.);
- `-format_whitelist mov,matroska`: only the MP4/MOV and Matroska/WebM demuxers may open the
  file, so playlists (HLS), concat lists, images and other formats are rejected before parsing;
- a fixed argv list (no shell) and a timeout.
"""

from __future__ import annotations

import json
import shutil
import subprocess  # nosec B404 - fixed argv list, no shell
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from seehere.core.config import Settings

ALLOWED_DEMUXERS = "mov,matroska"
WEBM_VIDEO = {"vp8", "vp9", "av1"}
WEBM_AUDIO = {"opus", "vorbis"}


class UploadRejected(Exception):
    """The upload is not an acceptable lecture video. `message` is safe to show to users."""

    def __init__(self, code: str, message: str, status: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


@dataclass(frozen=True)
class VideoProbe:
    format_name: str
    mime_type: str
    extension: str
    duration_s: float
    width: int | None
    height: int | None
    video_codec: str
    audio_codec: str
    raw: dict[str, Any]


def run_ffprobe(path: Path, settings: Settings) -> dict[str, Any]:
    binary = shutil.which(settings.ffprobe_bin)
    if binary is None:
        raise RuntimeError("ffprobe is not installed")
    argv = [
        binary,
        "-v",
        "error",
        "-protocol_whitelist",
        "file",
        "-format_whitelist",
        ALLOWED_DEMUXERS,
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        f"file:{path}",
    ]
    try:
        result = subprocess.run(  # noqa: S603 - argv list, no shell
            argv, capture_output=True, text=True, timeout=settings.ffprobe_timeout_s, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise UploadRejected("probe_timeout", "The file took too long to inspect.") from exc
    if result.returncode != 0:
        raise UploadRejected(
            "unsupported_format",
            "This file is not a supported video. Upload an MP4, MOV, WebM or MKV file.",
            status=415,
        )
    try:
        data: dict[str, Any] = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise UploadRejected("unsupported_format", "The file could not be read.", 415) from exc
    return data


def _container(format_name: str, video: str, audio: str, brand: str) -> tuple[str, str]:
    """(extension, MIME type) decided from the detected container and codecs."""
    if "matroska" in format_name:
        if video in WEBM_VIDEO and audio in WEBM_AUDIO:
            return ".webm", "video/webm"
        return ".mkv", "video/x-matroska"
    if brand.strip() == "qt":
        return ".mov", "video/quicktime"
    return ".mp4", "video/mp4"


def inspect_lecture_video(path: Path, settings: Settings) -> VideoProbe:
    data = run_ffprobe(path, settings)
    fmt: dict[str, Any] = data.get("format", {})
    streams: list[dict[str, Any]] = data.get("streams", [])
    video = next(
        (
            s
            for s in streams
            if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")
        ),
        None,
    )
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if video is None:
        raise UploadRejected("no_video_stream", "This file has no video track.")
    if audio is None:
        raise UploadRejected(
            "no_audio_stream",
            "This video has no audio track. SeeHere needs the lecturer's speech.",
        )

    try:
        duration = float(fmt.get("duration") or video.get("duration") or 0)
    except (TypeError, ValueError):
        duration = 0.0
    if duration <= 0:
        raise UploadRejected("unknown_duration", "The video's length could not be determined.")
    if duration > settings.max_video_duration_s:
        limit = settings.max_video_duration_s
        raise UploadRejected(
            "too_long",
            f"The video is {duration:.0f} seconds long. The limit is {limit} seconds.",
        )

    format_name = str(fmt.get("format_name", ""))
    video_codec = str(video.get("codec_name", "unknown"))
    audio_codec = str(audio.get("codec_name", "unknown"))
    brand = str(fmt.get("tags", {}).get("major_brand", ""))
    extension, mime = _container(format_name, video_codec, audio_codec, brand)

    # Keep the useful metadata, but not the temp path ffprobe echoes back.
    raw_format = {k: v for k, v in fmt.items() if k != "filename"}
    return VideoProbe(
        format_name=format_name,
        mime_type=mime,
        extension=extension,
        duration_s=round(duration, 3),
        width=video.get("width"),
        height=video.get("height"),
        video_codec=video_codec,
        audio_codec=audio_codec,
        raw={"format": raw_format, "streams": streams},
    )
