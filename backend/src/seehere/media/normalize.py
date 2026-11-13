"""Media preparation (pipeline stage "media", job kind `media.prepare`).

For a project's source video:
1. Re-inspect the stored file with ffprobe (the same content rules as upload).
2. Extract the first audio track as 16 kHz mono 16-bit PCM WAV, the input speech-to-text
   expects (Task 08), and verify the result with ffprobe.
3. Sample frames at `frame_sample_fps` (default 1 per second), scaled down to at most
   `frame_max_width`, as JPEGs. Frame n is the picture on screen at t = n / fps (the last
   decoded frame at or before that time), and its file is named by n (`-frame_pts`).
4. Replace any earlier outputs for this video in one transaction, so a retried or repeated
   run leaves exactly one set of outputs (the handler is idempotent). The same transaction
   queues speech-to-text (Task 08) for the new audio.

All work happens in a private temp directory; outputs are moved into place only after every
step succeeded. Corrupt or unsupported input fails permanently with a user-safe message.
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
from pathlib import Path

from sqlalchemy import delete, select

from seehere.db.enums import MediaKind
from seehere.db.models import Frame, MediaAsset
from seehere.jobs.errors import JobCancelled, PermanentJobError
from seehere.jobs.queue import ClaimedJob
from seehere.jobs.worker import JobContext
from seehere.media.ffmpeg import FFmpegCancelled, FFmpegError, input_args, run_ffmpeg
from seehere.media.probe import UploadRejected, inspect_lecture_video, inspect_wav
from seehere.media.storage import frames_dir, normalized_audio_path
from seehere.speech.transcribe import queue_transcription

log = logging.getLogger("seehere.media")

JOB_KIND = "media.prepare"
AUDIO_SAMPLE_RATE = 16_000


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def frame_time(index: int, fps: float) -> float:
    """Time in seconds of the frame whose -frame_pts file number is `index`."""
    return round(index / fps, 3)


def prepare_media(ctx: JobContext, job: ClaimedJob) -> None:
    settings, store = ctx.settings, ctx.store
    with ctx.session() as s:
        source = s.scalars(
            select(MediaAsset).where(
                MediaAsset.project_id == job.project_id,
                MediaAsset.kind == MediaKind.SOURCE_VIDEO,
            )
        ).first()
        if source is None:
            raise PermanentJobError("This project has no source video.")
        source_id, source_rel = source.id, source.storage_path
    src = store.resolve(source_rel)
    if not src.is_file():
        raise PermanentJobError("The uploaded video file is missing from storage.")

    ctx.progress("inspect", 0.0)
    try:
        probe = inspect_lecture_video(src, settings)
    except UploadRejected as exc:
        raise PermanentJobError(exc.message) from exc

    work = store.new_temp_dir()
    try:
        wav = work / "audio.wav"
        _ffmpeg(
            ctx,
            [
                *input_args(src),
                "-map",
                "0:a:0",
                "-vn",
                "-sn",
                "-dn",
                "-ac",
                "1",
                "-ar",
                str(AUDIO_SAMPLE_RATE),
                "-c:a",
                "pcm_s16le",
                "-f",
                "wav",
                f"file:{wav}",
            ],
            stage="audio",
            start=0.05,
            span=0.30,
            duration_s=probe.duration_s,
            failure="The audio track could not be decoded.",
        )
        try:
            audio = inspect_wav(wav, settings)
        except UploadRejected as exc:
            raise PermanentJobError("The extracted audio could not be read.") from exc
        if (audio.codec, audio.sample_rate, audio.channels) != (
            "pcm_s16le",
            AUDIO_SAMPLE_RATE,
            1,
        ) or audio.duration_s <= 0:
            raise PermanentJobError("The extracted audio is not usable.")

        fps = settings.frame_sample_fps
        out_frames = work / "frames"
        out_frames.mkdir(mode=0o700)
        _ffmpeg(
            ctx,
            [
                *input_args(src),
                "-map",
                "0:v:0",
                "-an",
                "-sn",
                "-dn",
                # round=up: slot n gets the last frame at or before n/fps, i.e. what is on
                # screen at that moment. (The default, round=near, takes up to half a slot later.)
                "-vf",
                f"fps=fps={fps}:round=up,scale=w='min({settings.frame_max_width},iw)':h=-2",
                "-fps_mode",
                "passthrough",
                "-frame_pts",
                "1",
                "-q:v",
                "3",
                "-f",
                "image2",
                f"file:{out_frames / '%06d.jpg'}",
            ],
            stage="frames",
            start=0.35,
            span=0.55,
            duration_s=probe.duration_s,
            failure="The video frames could not be decoded.",
        )
        names = sorted(p.name for p in out_frames.glob("*.jpg"))
        if not names:
            raise PermanentJobError("No video frames could be decoded.")

        ctx.progress("save", 0.95)
        ctx.check_cancelled()
        audio_rel = normalized_audio_path(job.project_id)
        frames_rel = frames_dir(job.project_id)
        audio_row = MediaAsset(
            project_id=job.project_id,
            kind=MediaKind.NORMALIZED_AUDIO,
            original_filename="audio_16k.wav",
            storage_path=audio_rel,
            mime_type="audio/wav",
            size_bytes=wav.stat().st_size,
            sha256=_sha256(wav),
            duration_s=audio.duration_s,
            audio_codec=audio.codec,
            probe={
                "sample_rate": audio.sample_rate,
                "channels": audio.channels,
                "frames": {"fps": fps, "count": len(names), "max_width": settings.frame_max_width},
            },
        )
        frame_rows = [
            Frame(
                media_asset_id=source_id,
                t_s=frame_time(int(Path(name).stem), fps),
                storage_path=f"{frames_rel}/{name}",
            )
            for name in names
        ]
        with ctx.session() as s:
            s.execute(
                delete(MediaAsset).where(
                    MediaAsset.project_id == job.project_id,
                    MediaAsset.kind == MediaKind.NORMALIZED_AUDIO,
                )
            )
            s.execute(delete(Frame).where(Frame.media_asset_id == source_id))
            s.flush()
            os.chmod(wav, 0o600)
            store.promote(wav, audio_rel)
            store.replace_dir(out_frames, frames_rel)
            s.add(audio_row)
            s.add_all(frame_rows)
            queue_transcription(s, job.project_id)
            s.commit()
        log.info(
            "project %s: %.1f s of 16 kHz audio, %d frames at %s fps",
            job.project_id,
            audio.duration_s,
            len(names),
            fps,
        )
        ctx.progress("save", 1.0)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _ffmpeg(
    ctx: JobContext,
    args: list[str],
    *,
    stage: str,
    start: float,
    span: float,
    duration_s: float,
    failure: str,
) -> None:
    ctx.progress(stage, start)
    try:
        run_ffmpeg(
            args,
            binary=ctx.settings.ffmpeg_bin,
            duration_s=duration_s,
            timeout_s=ctx.settings.ffmpeg_timeout_s,
            on_progress=lambda f: ctx.progress(stage, start + span * f),
            cancel=ctx.cancel_event,
        )
    except FFmpegCancelled as exc:
        raise JobCancelled from exc
    except FFmpegError as exc:
        log.warning("ffmpeg failed in %s stage: %s\n%s", stage, exc, exc.detail)
        if "timed out" in str(exc):
            raise  # may be load-related: let the worker retry it
        raise PermanentJobError(failure) from exc
