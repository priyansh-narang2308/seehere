"""Speech-to-text as a pipeline job, end to end: a video with real recorded speech, the real
worker, the real faster-whisper model and Postgres. No mocks of the recognizer."""

from __future__ import annotations

import re
import shutil
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from speech_clip import SpeechClip, make_speech_clip, make_speech_video
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from seehere.core.config import Settings
from seehere.db.enums import JobStatus, MediaKind, ProjectStatus
from seehere.db.models import Job, MediaAsset, Project, TranscriptSegment, TranscriptWord
from seehere.jobs import queue
from seehere.jobs.worker import Worker
from seehere.media import normalize
from seehere.media.storage import MediaStore, source_video_path
from seehere.pipeline import HANDLERS, start_pipeline
from seehere.providers.base import ProgressCallback, Transcript
from seehere.providers.stt_faster_whisper import FasterWhisperSTT
from seehere.speech import transcribe

Sessions = sessionmaker[Session]


@pytest.fixture(scope="module")
def clip(tmp_path_factory: pytest.TempPathFactory) -> SpeechClip:
    return make_speech_clip(tmp_path_factory.mktemp("speech"))


@pytest.fixture(scope="module")
def video(clip: SpeechClip, tmp_path_factory: pytest.TempPathFactory) -> Path:
    return make_speech_video(clip, tmp_path_factory.mktemp("video") / "lecture.mp4")


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(media_dir=tmp_path / "media", job_heartbeat_interval_s=0.2)


def _project(sessions: Sessions, settings: Settings, video: Path) -> uuid.UUID:
    with sessions() as s:
        project = Project(title="Lecture", rights_confirmed_at=datetime.now(UTC))
        s.add(project)
        s.flush()
        rel = source_video_path(project.id, ".mp4")
        media = MediaAsset(
            project_id=project.id,
            kind=MediaKind.SOURCE_VIDEO,
            original_filename=video.name,
            storage_path=rel,
            mime_type="video/mp4",
            size_bytes=video.stat().st_size,
            sha256="0" * 64,
        )
        s.add(media)
        s.flush()
        dest = MediaStore(settings.media_dir).resolve(rel)
        dest.parent.mkdir(parents=True)
        shutil.copyfile(video, dest)
        start_pipeline(s, project.id, media.id)
        s.commit()
        return project.id


def _jobs(sessions: Sessions, pid: uuid.UUID) -> dict[str, Job]:
    with sessions() as s:
        return {j.kind: j for j in s.scalars(select(Job).where(Job.project_id == pid))}


def _words(sessions: Sessions, pid: uuid.UUID) -> list[TranscriptWord]:
    with sessions() as s:
        return list(
            s.scalars(
                select(TranscriptWord)
                .join(MediaAsset, MediaAsset.id == TranscriptWord.media_asset_id)
                .where(MediaAsset.project_id == pid)
                .order_by(TranscriptWord.idx)
            )
        )


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _run_all(sessions: Sessions, settings: Settings) -> int:
    worker = Worker(HANDLERS, settings=settings, sessions=sessions)
    n = 0
    while worker.run_once():
        n += 1
    return n


def test_upload_to_timed_transcript(
    sessions: Sessions, settings: Settings, video: Path, clip: SpeechClip
) -> None:
    pid = _project(sessions, settings, video)
    # media, speech-to-text, scenes, on-screen text, visual units, and seen-versus-said (queued
    # by both speech-to-text and visual analysis, so it may run twice)
    assert _run_all(sessions, settings) in (6, 7)

    jobs = _jobs(sessions, pid)
    speech = jobs[transcribe.JOB_KIND]
    assert (speech.status, speech.progress, speech.stage, speech.error, speech.attempts) == (
        JobStatus.SUCCEEDED,
        1.0,
        "save",
        None,
        1,
    )
    with sessions() as s:
        assert s.get(Project, pid).status == ProjectStatus.UPLOADED  # type: ignore[union-attr]
        audio = s.scalars(
            select(MediaAsset).where(
                MediaAsset.project_id == pid, MediaAsset.kind == MediaKind.NORMALIZED_AUDIO
            )
        ).one()
        segments = list(
            s.scalars(
                select(TranscriptSegment)
                .where(TranscriptSegment.media_asset_id == audio.id)
                .order_by(TranscriptSegment.idx)
            )
        )
        meta = audio.probe["transcript"]

    words = _words(sessions, pid)
    assert [w.idx for w in words] == list(range(len(words)))
    assert [s.idx for s in segments] == list(range(len(segments)))
    assert "bar chart on the left" in " ".join(s.text for s in segments).lower()
    assert {w.segment_id for w in words} <= {s.id for s in segments}
    assert meta["provider"] == "faster-whisper:small.en"
    assert (meta["language"], meta["segments"], meta["words"]) == ("en", len(segments), len(words))

    # Times are stored in seconds of the source, and the measured pause survives the round trip.
    starts = [w.start_s for w in words]
    assert starts == sorted(starts)
    assert all(0 <= w.start_s <= w.end_s <= audio.duration_s for w in words)  # type: ignore[operator]
    norm = [_norm(w.text) for w in words]
    i = norm.index("left")
    assert norm[i + 1] == "sales"
    assert words[i].end_s == pytest.approx(clip.pause_start_s, abs=0.4)
    assert words[i + 1].start_s == pytest.approx(clip.pause_end_s, abs=0.4)


def test_running_again_replaces_the_transcript(
    sessions: Sessions, settings: Settings, video: Path
) -> None:
    pid = _project(sessions, settings, video)
    _run_all(sessions, settings)
    first = [(w.text, w.start_s) for w in _words(sessions, pid)]
    speech = _jobs(sessions, pid)[transcribe.JOB_KIND]
    with sessions() as s:
        s.execute(Job.__table__.update().where(Job.id == speech.id).values(status="failed"))
        s.commit()
        queue.retry(s, speech.id)
    assert _run_all(sessions, settings) == 2  # speech-to-text, then re-scoring
    assert [(w.text, w.start_s) for w in _words(sessions, pid)] == first
    with sessions() as s:
        assert s.scalar(select(func.count()).select_from(TranscriptSegment)) > 0
        assert s.scalar(select(func.count()).select_from(TranscriptWord)) == len(first)


def test_new_audio_requeues_the_same_speech_job(
    sessions: Sessions, settings: Settings, video: Path
) -> None:
    pid = _project(sessions, settings, video)
    _run_all(sessions, settings)
    jobs = _jobs(sessions, pid)
    with sessions() as s:  # media preparation runs again (e.g. a retry after a crash)
        prep = jobs[normalize.JOB_KIND]
        s.execute(Job.__table__.update().where(Job.id == prep.id).values(status="failed"))
        s.commit()
        queue.retry(s, prep.id)
    worker = Worker(
        {normalize.JOB_KIND: HANDLERS[normalize.JOB_KIND]}, settings=settings, sessions=sessions
    )
    assert worker.run_once()

    after = _jobs(sessions, pid)
    speech = after[transcribe.JOB_KIND]
    assert len(after) == 6 and speech.id == jobs[transcribe.JOB_KIND].id
    assert (speech.status, speech.attempts, speech.progress) == (JobStatus.QUEUED, 0, 0.0)
    assert _words(sessions, pid) == []  # the old transcript went with the old audio
    with sessions() as s:
        assert s.get(Project, pid).status == ProjectStatus.PROCESSING  # type: ignore[union-attr]
    # speech, scenes, OCR, visual units, and seen-versus-said re-queued (it may run twice)
    assert _run_all(sessions, settings) in (5, 6)
    assert len(_words(sessions, pid)) > 10


def test_missing_audio_fails_permanently(
    sessions: Sessions, settings: Settings, video: Path
) -> None:
    pid = _project(sessions, settings, video)
    worker = Worker(
        {normalize.JOB_KIND: HANDLERS[normalize.JOB_KIND]}, settings=settings, sessions=sessions
    )
    worker.run_once()
    (settings.media_dir / "projects" / str(pid) / "audio_16k.wav").unlink()
    _run_all(sessions, settings)
    speech = _jobs(sessions, pid)[transcribe.JOB_KIND]
    assert (speech.status, speech.attempts, speech.error) == (
        JobStatus.FAILED,
        1,
        "The prepared audio is missing. Run media preparation again.",
    )


def test_model_that_cannot_load_is_retried_with_a_clear_message(
    sessions: Sessions, tmp_path: Path, video: Path
) -> None:
    settings = Settings(
        media_dir=tmp_path / "media",
        job_heartbeat_interval_s=0.2,
        local_stt_compute_type="no-such-type",
    )
    pid = _project(sessions, settings, video)
    _run_all(sessions, settings)  # the speech job is re-queued with a backoff delay
    speech = _jobs(sessions, pid)[transcribe.JOB_KIND]
    assert (speech.status, speech.attempts, speech.error) == (
        JobStatus.QUEUED,
        1,
        "The speech recognition model could not be loaded.",
    )
    assert speech.run_after > speech.updated_at


def test_cancel_during_recognition(
    sessions: Sessions, settings: Settings, video: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = _project(sessions, settings, video)

    class CancelMidway(FasterWhisperSTT):
        """The real recognizer; cancellation is requested once it reports progress."""

        def transcribe(
            self,
            audio_path: Path,
            language: str | None = None,
            progress: ProgressCallback | None = None,
        ) -> Transcript:
            def on_progress(f: float) -> None:
                with sessions() as s:
                    queue.request_cancel(s, _jobs(sessions, pid)[transcribe.JOB_KIND].id)
                time.sleep(0.3)  # past the progress-write throttle, so the request is read
                assert progress
                progress(f)

            return super().transcribe(audio_path, language, on_progress)

    monkeypatch.setattr(transcribe, "make_stt", lambda s: CancelMidway(s.local_stt_model))
    _run_all(sessions, settings)
    speech = _jobs(sessions, pid)[transcribe.JOB_KIND]
    assert speech.status == JobStatus.CANCELLED
    assert _words(sessions, pid) == []
