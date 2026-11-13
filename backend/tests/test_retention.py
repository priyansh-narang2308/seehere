"""Retention sweep: expired projects lose their files and rows; nothing else is touched."""

from __future__ import annotations

import os
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, sessionmaker

from seehere.core.config import Settings
from seehere.db.enums import JobStatus, MediaKind
from seehere.db.models import Job, MediaAsset, Project
from seehere.jobs import queue
from seehere.jobs.retention import sweep
from seehere.media.storage import MediaStore, UnsafePathError, project_dir

Sessions = sessionmaker[Session]


def _project_with_files(sessions: Sessions, store: MediaStore, expires_in: timedelta) -> uuid.UUID:
    now = datetime.now(UTC)
    with sessions() as s:
        p = Project(title="Lecture", rights_confirmed_at=now, expires_at=now + expires_in)
        s.add(p)
        s.flush()
        rel = f"{project_dir(p.id)}/source.mp4"
        s.add(
            MediaAsset(
                project_id=p.id,
                kind=MediaKind.SOURCE_VIDEO,
                original_filename="a.mp4",
                storage_path=rel,
                mime_type="video/mp4",
                size_bytes=3,
                sha256="0" * 64,
            )
        )
        s.commit()
    path = store.resolve(rel)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"abc")
    (path.parent / "frames").mkdir()
    (path.parent / "frames" / "000000.jpg").write_bytes(b"jpg")
    return p.id


@pytest.fixture
def store(tmp_path: Path) -> MediaStore:
    return MediaStore(tmp_path / "media")


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(media_dir=tmp_path / "media")


def test_sweep_deletes_only_expired_projects(
    sessions: Sessions, store: MediaStore, settings: Settings
) -> None:
    expired = _project_with_files(sessions, store, timedelta(minutes=-1))
    alive = _project_with_files(sessions, store, timedelta(hours=1))
    with sessions() as s:
        queue.enqueue(s, project_id=expired, kind="media.prepare", idempotency_key="k")
        s.commit()
        assert sweep(s, store, settings) == [expired]
        assert s.scalar(select(func.count()).select_from(Project)) == 1
        assert s.scalar(select(func.count()).select_from(MediaAsset)) == 1
        assert s.scalar(select(func.count()).select_from(Job)) == 0  # cascaded
    assert not store.resolve(project_dir(expired)).exists()
    assert (store.resolve(project_dir(alive)) / "source.mp4").read_bytes() == b"abc"


def test_sweep_waits_for_a_running_job(
    sessions: Sessions, store: MediaStore, settings: Settings
) -> None:
    pid = _project_with_files(sessions, store, timedelta(minutes=-1))
    with sessions() as s:
        job = queue.enqueue(s, project_id=pid, kind="media.prepare", idempotency_key="k")
        s.execute(update(Job).where(Job.id == job.id).values(status=JobStatus.RUNNING))
        s.commit()
        assert sweep(s, store, settings) == []
        s.execute(update(Job).where(Job.id == job.id).values(status=JobStatus.SUCCEEDED))
        s.commit()
        assert sweep(s, store, settings) == [pid]


def test_sweep_is_idempotent_when_files_are_already_gone(
    sessions: Sessions, store: MediaStore, settings: Settings
) -> None:
    pid = _project_with_files(sessions, store, timedelta(minutes=-1))
    store.remove_tree(project_dir(pid))
    with sessions() as s:
        assert sweep(s, store, settings) == [pid]


def test_sweep_removes_only_old_temp_entries(
    sessions: Sessions, store: MediaStore, settings: Settings
) -> None:
    old_file = store.new_temp_file()
    old_dir = store.new_temp_dir()
    (old_dir / "x.jpg").write_bytes(b"1")
    new_file = store.new_temp_file()
    long_ago = time.time() - 7 * 3600  # settings.temp_max_age_hours is 6
    for p in (old_file, old_dir):
        os.utime(p, (long_ago, long_ago))
    with sessions() as s:
        sweep(s, store, settings)
    assert not old_file.exists() and not old_dir.exists()
    assert new_file.exists()


def test_remove_tree_refuses_symlinks_and_escapes(tmp_path: Path, store: MediaStore) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep")
    (store.root / "projects").mkdir(parents=True)
    (store.root / "projects" / "link").symlink_to(outside)
    with pytest.raises(UnsafePathError):
        store.remove_tree("projects/link")
    with pytest.raises(UnsafePathError):
        store.remove_tree("../outside")
    assert (outside / "keep.txt").read_text() == "keep"
