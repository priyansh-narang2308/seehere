"""A project with a stored source video and its pipeline queued, plus a worker loop."""

from __future__ import annotations

import shutil
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from seehere.core.config import Settings
from seehere.db.enums import JobStatus, MediaKind
from seehere.db.models import Job, MediaAsset, Project, TranscriptSegment, TranscriptWord
from seehere.jobs.worker import Worker
from seehere.media.storage import MediaStore, source_video_path
from seehere.pipeline import HANDLERS, start_pipeline
from seehere.vision.coverage import queue_coverage

Sessions = sessionmaker[Session]


def add_project(
    sessions: Sessions, settings: Settings, video: Path, title: str = "Deck"
) -> uuid.UUID:
    with sessions() as s:
        project = Project(title=video.stem, rights_confirmed_at=datetime.now(UTC))
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


def run_jobs(sessions: Sessions, settings: Settings, kinds: Iterable[str]) -> None:
    """Run queued jobs of these kinds until none is left (others stay queued)."""
    worker = Worker({k: HANDLERS[k] for k in kinds}, settings=settings, sessions=sessions)
    while worker.run_once():
        pass


def say(sessions: Sessions, pid: uuid.UUID, words: list[tuple[float, str]]) -> None:
    """Write transcript words as speech-to-text would, mark it done, and queue scoring."""
    with sessions() as s:
        audio = s.scalars(
            select(MediaAsset).where(
                MediaAsset.project_id == pid, MediaAsset.kind == MediaKind.NORMALIZED_AUDIO
            )
        ).one()
        seg = TranscriptSegment(
            media_asset_id=audio.id,
            idx=0,
            start_s=words[0][0],
            end_s=words[-1][0] + 0.3,
            text=" ".join(w for _, w in words),
        )
        s.add(seg)
        s.flush()
        s.add_all(
            TranscriptWord(
                segment_id=seg.id,
                media_asset_id=audio.id,
                idx=i,
                start_s=t,
                end_s=t + 0.3,
                text=w,
                confidence=0.9,
            )
            for i, (t, w) in enumerate(words)
        )
        s.execute(  # as if speech-to-text finished
            update(Job)
            .where(Job.project_id == pid, Job.kind == "speech.transcribe")
            .values(status=JobStatus.SUCCEEDED)
        )
        queue_coverage(s, pid)
        s.commit()
