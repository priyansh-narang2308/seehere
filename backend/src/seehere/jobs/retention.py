"""Retention (ADR-009): delete projects whose `expires_at` has passed.

Each expired project is locked (FOR UPDATE SKIP LOCKED, so two workers never sweep the same
one), its media directory is removed, and its rows are deleted in the same transaction (the
database cascades to every derived row). If the commit fails after the files are gone, the next
sweep finds the row again and finishes the job; file removal is idempotent. Projects with a
running job are skipped until the job ends.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import delete, exists, func, select
from sqlalchemy.orm import Session

from seehere.core.config import Settings
from seehere.db.enums import JobStatus
from seehere.db.models import Job, Project
from seehere.media.storage import MediaStore, project_dir

log = logging.getLogger("seehere.retention")


def sweep(
    session: Session, store: MediaStore, settings: Settings, limit: int = 50
) -> list[uuid.UUID]:
    """Delete up to `limit` expired projects and stale temp files. Returns the project IDs."""
    running = exists().where(Job.project_id == Project.id, Job.status == JobStatus.RUNNING)
    ids = list(
        session.scalars(
            select(Project.id)
            .where(Project.expires_at < func.now(), ~running)
            .order_by(Project.expires_at)
            .limit(limit)
            .with_for_update(skip_locked=True, of=Project)
        )
    )
    deleted: list[uuid.UUID] = []
    for project_id in ids:
        try:
            store.remove_tree(project_dir(project_id))
        except OSError:
            log.exception("could not delete media for project %s; will retry", project_id)
            continue
        session.execute(delete(Project).where(Project.id == project_id))
        deleted.append(project_id)
    session.commit()
    for project_id in deleted:
        log.info("deleted expired project %s", project_id)
    removed = store.clean_temp(settings.temp_max_age_hours * 3600)
    if removed:
        log.info("removed %d stale temp entries", removed)
    return deleted
