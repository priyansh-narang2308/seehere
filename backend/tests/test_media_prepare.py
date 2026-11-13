"""Media preparation, end to end: real videos made by ffmpeg, the real worker and Postgres.

The main fixture is a video whose brightness rises steadily with time, so a sampled frame's
content proves which moment it came from. Each frame is compared with a reference frame
decoded independently at the timestamp we stored.
"""

from __future__ import annotations

import shutil
import subprocess
import threading
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from seehere.core.config import Settings
from seehere.db.enums import JobStatus, MediaKind
from seehere.db.models import Frame, Job, MediaAsset, Project
from seehere.jobs import queue
from seehere.jobs.worker import JobContext, Worker
from seehere.media.ffmpeg import FFmpegCancelled, FFmpegError, input_args, run_ffmpeg
from seehere.media.normalize import JOB_KIND, frame_time, prepare_media
from seehere.media.storage import MediaStore, source_video_path
from seehere.pipeline import HANDLERS, start_pipeline

Sessions = sessionmaker[Session]


def _ffmpeg(*args: str) -> bytes:
    return subprocess.run(
        ["ffmpeg", "-v", "error", "-y", *args], check=True, capture_output=True, timeout=120
    ).stdout


@pytest.fixture(scope="module")
def ramp(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """8 s, 640x360 at 10 fps, brightness rising with time, 440 Hz tone."""
    out = tmp_path_factory.mktemp("ramp") / "ramp.mp4"
    _ffmpeg(
        "-f",
        "lavfi",
        "-i",
        "color=c=black:s=640x360:r=10:d=8,geq=lum='min(T*25\\,255)':cb=128:cr=128",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:duration=8",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-shortest",
        str(out),
    )
    return out


def _luma(image: Path, *, at: float | None = None) -> int:
    """Average brightness (0-255) of an image, or of a video frame decoded at `at` seconds."""
    seek = ["-ss", f"{at}"] if at is not None else []
    out = _ffmpeg(
        *seek,
        "-i",
        str(image),
        "-frames:v",
        "1",
        "-vf",
        "scale=1:1",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "gray",
        "-",
    )
    return out[0]


def _settings(tmp_path: Path, **kw: object) -> Settings:
    values: dict = {"media_dir": tmp_path / "media", "job_heartbeat_interval_s": 0.2}
    values.update(kw)
    return Settings(**values)


def _project(sessions: Sessions, settings: Settings, video: Path, ext: str = ".mp4") -> uuid.UUID:
    store = MediaStore(settings.media_dir)
    with sessions() as s:
        project = Project(title="Lecture", rights_confirmed_at=datetime.now(UTC))
        s.add(project)
        s.flush()
        rel = source_video_path(project.id, ext)
        media = MediaAsset(
            project_id=project.id,
            kind=MediaKind.SOURCE_VIDEO,
            original_filename=video.name,
            storage_path=rel,
            mime_type="video/mp4",
            size_bytes=video.stat().st_size,
            sha256="0" * 64,
            duration_s=8,
        )
        s.add(media)
        s.flush()
        dest = store.resolve(rel)
        dest.parent.mkdir(parents=True)
        shutil.copyfile(video, dest)
        start_pipeline(s, project.id, media.id)
        s.commit()
        return project.id


def _run(sessions: Sessions, settings: Settings) -> Worker:
    worker = Worker(HANDLERS, settings=settings, sessions=sessions)
    assert worker.run_once() is True
    return worker


def _job(sessions: Sessions, project_id: uuid.UUID) -> Job:
    with sessions() as s:
        return s.scalars(select(Job).where(Job.project_id == project_id)).one()


def _outputs(sessions: Sessions, project_id: uuid.UUID) -> tuple[list[MediaAsset], list[Frame]]:
    with sessions() as s:
        audio = list(
            s.scalars(
                select(MediaAsset).where(
                    MediaAsset.project_id == project_id,
                    MediaAsset.kind == MediaKind.NORMALIZED_AUDIO,
                )
            )
        )
        frames = list(
            s.scalars(
                select(Frame)
                .join(MediaAsset, Frame.media_asset_id == MediaAsset.id)
                .where(MediaAsset.project_id == project_id)
                .order_by(Frame.t_s)
            )
        )
        return audio, frames


def _temp_entries(settings: Settings) -> list[Path]:
    tmp = settings.media_dir / "tmp"
    return list(tmp.iterdir()) if tmp.exists() else []


def test_prepares_16k_mono_audio_and_correctly_timed_frames(
    sessions: Sessions, ramp: Path, tmp_path: Path
) -> None:
    settings = _settings(tmp_path)
    pid = _project(sessions, settings, ramp)
    _run(sessions, settings)

    job = _job(sessions, pid)
    assert (job.status, job.progress, job.stage, job.error) == (
        JobStatus.SUCCEEDED,
        1.0,
        "save",
        None,
    )
    [audio], frames = _outputs(sessions, pid)
    store = MediaStore(settings.media_dir)

    wav = store.resolve(audio.storage_path)
    assert audio.storage_path == f"projects/{pid}/audio_16k.wav"
    assert (audio.mime_type, audio.audio_codec) == ("audio/wav", "pcm_s16le")
    assert audio.probe is not None
    assert (audio.probe["sample_rate"], audio.probe["channels"]) == (16000, 1)
    assert audio.duration_s == pytest.approx(8.0, abs=0.05)
    # 16-bit mono at 16 kHz: 32,000 bytes per second plus a small header.
    assert abs(wav.stat().st_size - 32000 * 8) < 1024
    assert audio.size_bytes == wav.stat().st_size
    assert wav.stat().st_mode & 0o777 == 0o600

    assert [f.t_s for f in frames] == [0, 1, 2, 3, 4, 5, 6, 7]
    for frame in frames:
        image = store.resolve(frame.storage_path)
        assert image.read_bytes()[:2] == b"\xff\xd8"  # JPEG
        expected = _luma(ramp, at=frame.t_s)
        assert abs(_luma(image) - expected) <= 6, f"frame at {frame.t_s}s shows another moment"
    # Brightness must actually change between frames, or the check above proves nothing.
    assert (
        _luma(store.resolve(frames[-1].storage_path)) - _luma(store.resolve(frames[0].storage_path))
        > 150
    )
    assert _temp_entries(settings) == []
    assert job.attempts == 1


def test_frame_rate_and_width_limits_are_applied(
    sessions: Sessions, ramp: Path, tmp_path: Path
) -> None:
    settings = _settings(tmp_path, frame_sample_fps=2.0, frame_max_width=320)
    pid = _project(sessions, settings, ramp)
    _run(sessions, settings)
    _, frames = _outputs(sessions, pid)
    assert [f.t_s for f in frames] == [i / 2 for i in range(16)]
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=width,height",
            "-of",
            "csv=p=0",
            str(MediaStore(settings.media_dir).resolve(frames[0].storage_path)),
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert probe == "320,180"


def test_running_again_replaces_outputs_instead_of_duplicating(
    sessions: Sessions, ramp: Path, tmp_path: Path
) -> None:
    settings = _settings(tmp_path)
    pid = _project(sessions, settings, ramp)
    _run(sessions, settings)
    job = _job(sessions, pid)
    with sessions() as s:  # a successful job re-run, as a retry or a manual re-run would do
        s.execute(Job.__table__.update().where(Job.id == job.id).values(status=JobStatus.FAILED))
        s.commit()
        queue.retry(s, job.id)
    _run(sessions, settings)
    audio, frames = _outputs(sessions, pid)
    assert len(audio) == 1 and len(frames) == 8
    files = sorted(
        p.name for p in (settings.media_dir / "projects" / str(pid)).rglob("*") if p.is_file()
    )
    assert len(files) == 1 + 1 + 8  # source, audio, frames


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (
            b"#EXTM3U\n#EXTINF:1,\nhttp://127.0.0.1:9/x.ts\n#EXT-X-ENDLIST\n",
            "This file is not a supported video. Upload an MP4, MOV, WebM or MKV file.",
        ),
        (
            b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 4000,  # MP4 header, no movie data
            "This file is not a supported video. Upload an MP4, MOV, WebM or MKV file.",
        ),
    ],
)
def test_malformed_input_fails_permanently_without_outputs(
    sessions: Sessions, tmp_path: Path, content: bytes, message: str
) -> None:
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(content)
    settings = _settings(tmp_path)
    pid = _project(sessions, settings, bad)
    _run(sessions, settings)
    job = _job(sessions, pid)
    assert (job.status, job.attempts, job.error) == (JobStatus.FAILED, 1, message)
    assert _outputs(sessions, pid) == ([], [])
    assert _temp_entries(settings) == []


def test_truncated_video_is_rejected(sessions: Sessions, ramp: Path, tmp_path: Path) -> None:
    data = ramp.read_bytes()
    cut = tmp_path / "cut.mp4"
    cut.write_bytes(data[: len(data) // 2])  # the index (moov) is written at the end
    settings = _settings(tmp_path)
    pid = _project(sessions, settings, cut)
    _run(sessions, settings)
    job = _job(sessions, pid)
    assert job.status is JobStatus.FAILED and job.error
    assert _outputs(sessions, pid) == ([], [])


def test_missing_source_file_fails_permanently(
    sessions: Sessions, ramp: Path, tmp_path: Path
) -> None:
    settings = _settings(tmp_path)
    pid = _project(sessions, settings, ramp)
    shutil.rmtree(settings.media_dir / "projects" / str(pid))
    _run(sessions, settings)
    job = _job(sessions, pid)
    assert (job.status, job.error) == (
        JobStatus.FAILED,
        "The uploaded video file is missing from storage.",
    )


def test_cancelled_preparation_leaves_no_outputs(
    sessions: Sessions, ramp: Path, tmp_path: Path
) -> None:
    settings = _settings(tmp_path)
    pid = _project(sessions, settings, ramp)
    with sessions() as s:
        claimed = queue.claim(s, "w", [JOB_KIND])
    assert claimed is not None
    ctx = JobContext(claimed, "w", settings, MediaStore(settings.media_dir), sessions)
    calls = 0

    def cancel_during_frames(stage: str, fraction: float, original=ctx.progress) -> None:  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        if stage == "frames":
            ctx.cancel_event.set()
        original(stage, fraction)

    ctx.progress = cancel_during_frames  # type: ignore[method-assign]
    from seehere.jobs.errors import JobCancelled

    with pytest.raises(JobCancelled):
        prepare_media(ctx, claimed)
    assert calls > 0
    assert _outputs(sessions, pid) == ([], [])
    assert _temp_entries(settings) == []


def test_upload_style_enqueue_is_idempotent(sessions: Sessions, ramp: Path, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    pid = _project(sessions, settings, ramp)
    with sessions() as s:
        media_id = s.scalars(select(MediaAsset.id).where(MediaAsset.project_id == pid)).one()
        start_pipeline(s, pid, media_id)
        s.commit()
        assert s.scalar(select(func.count()).select_from(Job)) == 1


def test_frame_time_formula() -> None:
    assert [frame_time(n, 1.0) for n in (0, 1, 59)] == [0, 1, 59]
    assert [frame_time(n, 0.5) for n in (0, 1, 3)] == [0, 2, 6]
    assert frame_time(1, 3.0) == 0.333


# --- the ffmpeg runner -----------------------------------------------------------------------

LONG_INPUT = ["-f", "lavfi", "-i", "testsrc=size=320x240:rate=25:duration=600"]


def test_runner_reports_progress_to_completion(tmp_path: Path) -> None:
    seen: list[float] = []
    run_ffmpeg(
        ["-f", "lavfi", "-i", "testsrc=size=640x360:rate=25:duration=20", "-f", "null", "-"],
        binary="ffmpeg",
        duration_s=20,
        timeout_s=60,
        on_progress=seen.append,
    )
    assert seen[-1] == 1.0
    assert seen == sorted(seen)


def test_runner_kills_ffmpeg_when_cancelled() -> None:
    cancel = threading.Event()
    threading.Timer(0.3, cancel.set).start()
    started = time.monotonic()
    with pytest.raises(FFmpegCancelled):
        run_ffmpeg(
            [*LONG_INPUT, "-f", "null", "-"],
            binary="ffmpeg",
            duration_s=600,
            timeout_s=60,
            cancel=cancel,
        )
    assert time.monotonic() - started < 5


def test_runner_enforces_its_timeout() -> None:
    with pytest.raises(FFmpegError, match="timed out"):
        run_ffmpeg([*LONG_INPUT, "-f", "null", "-"], binary="ffmpeg", duration_s=600, timeout_s=0.5)


def test_runner_reports_failures_with_detail_for_logs(tmp_path: Path) -> None:
    with pytest.raises(FFmpegError) as info:
        run_ffmpeg(
            [*input_args(tmp_path / "missing.mp4"), "-f", "null", "-"],
            binary="ffmpeg",
            duration_s=1,
            timeout_s=10,
        )
    assert "exited with code" in str(info.value)
    assert info.value.detail


def test_runner_inputs_cannot_reach_the_network(tmp_path: Path) -> None:
    playlist = tmp_path / "list.m3u8"
    playlist.write_text("#EXTM3U\n#EXTINF:1,\nhttp://127.0.0.1:9/x.ts\n#EXT-X-ENDLIST\n")
    with pytest.raises(FFmpegError):
        run_ffmpeg(
            [*input_args(playlist, demuxers="hls"), "-f", "null", "-"],
            binary="ffmpeg",
            duration_s=1,
            timeout_s=10,
        )
