"""A project with a stored source video and its pipeline queued, plus a worker loop."""

from __future__ import annotations

import shutil
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from seehere.core.config import Settings
from seehere.db.enums import MediaKind
from seehere.db.models import MediaAsset, Project
from seehere.jobs.worker import Worker
from seehere.media.storage import MediaStore, source_video_path
from seehere.pipeline import HANDLERS, start_pipeline

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
