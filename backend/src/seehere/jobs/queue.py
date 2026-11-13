"""Queue operations on the `job` table.

Delivery is at-least-once: a job whose worker dies is re-queued after its heartbeat goes stale,
so handlers must be idempotent (they replace their outputs rather than append to them).

Every state change after a claim is guarded by `locked_by = <worker id>`, so a worker that lost
its lease (because its job was recovered and claimed by another worker) cannot overwrite the
newer state. All timestamps come from the database clock, never from worker clocks.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import and_, case, exists, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from seehere.db.enums import JobStatus, ProjectStatus
from seehere.db.models import Job, Project

ACTIVE = (JobStatus.QUEUED, JobStatus.RUNNING)
STALE_MESSAGE = "The worker running this job stopped responding."


@dataclass(frozen=True)
class ClaimedJob:
    """A snapshot of a job at claim time, handed to its handler."""

    id: uuid.UUID
    project_id: uuid.UUID
    kind: str
    payload: dict[str, Any]
    attempts: int
    max_attempts: int


def enqueue(
    session: Session,
    *,
    project_id: uuid.UUID,
    kind: str,
    idempotency_key: str,
    payload: dict[str, Any] | None = None,
    max_attempts: int = 3,
) -> Job:
    """Add a job unless one with the same idempotency key exists; return the job either way.

    Does not commit, so the caller can enqueue in the same transaction as the data it refers to.
    """
    stmt = (
        insert(Job)
        .values(
            id=uuid.uuid4(),
            project_id=project_id,
            kind=kind,
            idempotency_key=idempotency_key,
            payload=payload or {},
            max_attempts=max_attempts,
        )
        .on_conflict_do_nothing(index_elements=[Job.idempotency_key])
    )
    session.execute(stmt)
    job = session.scalars(select(Job).where(Job.idempotency_key == idempotency_key)).one()
    return job


def claim(session: Session, worker_id: str, kinds: list[str]) -> ClaimedJob | None:
    """Atomically take the next runnable job. Concurrent workers never get the same job:
    the row is locked with FOR UPDATE SKIP LOCKED, so a second worker skips it."""
    next_id = (
        select(Job.id)
        .where(Job.status == JobStatus.QUEUED, Job.run_after <= func.now(), Job.kind.in_(kinds))
        .order_by(Job.run_after, Job.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
        .scalar_subquery()
    )
    row = session.execute(
        update(Job)
        .where(Job.id == next_id)
        .values(
            status=JobStatus.RUNNING,
            attempts=Job.attempts + 1,
            locked_by=worker_id,
            locked_at=func.now(),
            heartbeat_at=func.now(),
            cancel_requested=False,
            error=None,
        )
        .returning(Job.id, Job.project_id, Job.kind, Job.payload, Job.attempts, Job.max_attempts)
        .execution_options(synchronize_session=False)
    ).one_or_none()
    session.commit()
    if row is None:
        return None
    return ClaimedJob(*row)


def _owned(job_id: uuid.UUID, worker_id: str) -> Any:
    return and_(Job.id == job_id, Job.locked_by == worker_id, Job.status == JobStatus.RUNNING)


def heartbeat(session: Session, job_id: uuid.UUID, worker_id: str) -> bool | None:
    """Refresh the lease. Returns whether cancellation was requested, or None if the lease is
    lost (the job is no longer ours)."""
    value = session.execute(
        update(Job)
        .where(_owned(job_id, worker_id))
        .values(heartbeat_at=func.now())
        .returning(Job.cancel_requested)
        .execution_options(synchronize_session=False)
    ).scalar_one_or_none()
    session.commit()
    return value


def report_progress(
    session: Session, job_id: uuid.UUID, worker_id: str, stage: str, progress: float
) -> bool | None:
    """Store progress (0..1) and refresh the lease. Same return value as `heartbeat`."""
    value = session.execute(
        update(Job)
        .where(_owned(job_id, worker_id))
        .values(stage=stage, progress=min(max(progress, 0.0), 1.0), heartbeat_at=func.now())
        .returning(Job.cancel_requested)
        .execution_options(synchronize_session=False)
    ).scalar_one_or_none()
    session.commit()
    return value


def complete(session: Session, job_id: uuid.UUID, worker_id: str) -> bool:
    result = session.execute(
        update(Job)
        .where(_owned(job_id, worker_id))
        .values(
            status=JobStatus.SUCCEEDED,
            progress=1.0,
            locked_by=None,
            finished_at=func.now(),
            error=None,
        )
        .returning(Job.id)
        .execution_options(synchronize_session=False)
    ).first()
    session.commit()
    return result is not None


def retry_delay_s(attempt: int, base_s: float, max_s: float) -> float:
    """Exponential backoff: base, 2*base, 4*base, ... capped at max_s. `attempt` starts at 1."""
    return float(min(max_s, base_s * 2 ** max(attempt - 1, 0)))


def fail(
    session: Session,
    job: ClaimedJob,
    worker_id: str,
    message: str,
    *,
    retryable: bool,
    base_s: float,
    max_s: float,
) -> JobStatus | None:
    """Record a failure. Retryable failures with attempts left are re-queued after a backoff
    delay; others end the job. Returns the new status, or None if the lease was lost."""
    if retryable and job.attempts < job.max_attempts:
        delay = timedelta(seconds=retry_delay_s(job.attempts, base_s, max_s))
        values: dict[str, Any] = {
            "status": JobStatus.QUEUED,
            "run_after": func.now() + delay,
            "locked_by": None,
            "error": message,
        }
    else:
        values = {
            "status": JobStatus.FAILED,
            "locked_by": None,
            "finished_at": func.now(),
            "error": message,
        }
    status = session.execute(
        update(Job)
        .where(_owned(job.id, worker_id))
        .values(**values)
        .returning(Job.status)
        .execution_options(synchronize_session=False)
    ).scalar_one_or_none()
    session.commit()
    return status


def mark_cancelled(session: Session, job_id: uuid.UUID, worker_id: str) -> bool:
    result = session.execute(
        update(Job)
        .where(_owned(job_id, worker_id))
        .values(
            status=JobStatus.CANCELLED,
            locked_by=None,
            finished_at=func.now(),
            error="Cancelled on request.",
        )
        .returning(Job.id)
        .execution_options(synchronize_session=False)
    ).first()
    session.commit()
    return result is not None


def request_cancel(session: Session, job_id: uuid.UUID) -> Job | None:
    """Cancel a queued job at once, or ask its worker to stop a running one. Finished jobs are
    left as they are. Returns the job, or None if it does not exist."""
    session.execute(
        update(Job)
        .where(Job.id == job_id, Job.status == JobStatus.QUEUED)
        .values(
            status=JobStatus.CANCELLED,
            finished_at=func.now(),
            error="Cancelled on request.",
        )
        .execution_options(synchronize_session=False)
    )
    session.execute(
        update(Job)
        .where(Job.id == job_id, Job.status == JobStatus.RUNNING)
        .values(cancel_requested=True)
        .execution_options(synchronize_session=False)
    )
    session.commit()
    return session.get(Job, job_id, populate_existing=True)


def retry(session: Session, job_id: uuid.UUID) -> Job | None:
    """Re-queue a failed or cancelled job as a fresh run (attempts reset). Returns the job if it
    was re-queued, or None if it is not in a retryable state."""
    result = session.execute(
        update(Job)
        .where(Job.id == job_id, Job.status.in_([JobStatus.FAILED, JobStatus.CANCELLED]))
        .values(
            status=JobStatus.QUEUED,
            attempts=0,
            progress=0.0,
            stage=None,
            error=None,
            cancel_requested=False,
            run_after=func.now(),
            finished_at=None,
            locked_by=None,
        )
        .returning(Job.id)
        .execution_options(synchronize_session=False)
    ).first()
    session.commit()
    if result is None:
        return None
    return session.get(Job, job_id, populate_existing=True)


def recover_stale(session: Session, stale_after_s: float) -> list[uuid.UUID]:
    """Re-queue running jobs whose worker stopped heartbeating (crashed, killed, lost network).
    Jobs out of attempts fail; jobs with a pending cancel request are cancelled."""
    cutoff = func.now() - timedelta(seconds=stale_after_s)
    out_of_attempts = Job.attempts >= Job.max_attempts
    rows = session.execute(
        update(Job)
        .where(Job.status == JobStatus.RUNNING, Job.heartbeat_at < cutoff)
        .values(
            status=case(
                (Job.cancel_requested, JobStatus.CANCELLED.value),
                (out_of_attempts, JobStatus.FAILED.value),
                else_=JobStatus.QUEUED.value,
            ),
            finished_at=case((Job.cancel_requested | out_of_attempts, func.now()), else_=None),
            error=case((Job.cancel_requested, "Cancelled on request."), else_=STALE_MESSAGE),
            locked_by=None,
            run_after=func.now(),
        )
        .returning(Job.id)
        .execution_options(synchronize_session=False)
    ).all()
    session.commit()
    return [r[0] for r in rows]


def refresh_project_status(session: Session, project_id: uuid.UUID) -> None:
    """Derive the project's status from its jobs: processing while any job is queued or running,
    failed if the latest run of some job failed, otherwise uploaded. ("ready" is set only when
    the full pipeline exists and finishes; it is not reachable yet.)"""
    active = exists().where(Job.project_id == project_id, Job.status.in_(ACTIVE))
    failed = exists().where(Job.project_id == project_id, Job.status == JobStatus.FAILED)
    session.execute(
        update(Project)
        .where(Project.id == project_id, Project.status != ProjectStatus.READY)
        .values(
            status=case(
                (active, ProjectStatus.PROCESSING.value),
                (failed, ProjectStatus.FAILED.value),
                else_=ProjectStatus.UPLOADED.value,
            )
        )
        .execution_options(synchronize_session=False)
    )
    session.commit()
