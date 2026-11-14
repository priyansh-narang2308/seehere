"""Queue and worker tests against real Postgres with committed transactions, so separate
connections (threads, and a real killed process) compete exactly as production workers do."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import textwrap
import threading
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import Engine, func, select, text, update
from sqlalchemy.orm import Session, sessionmaker

from seehere.core.config import Settings
from seehere.db.enums import JobStatus, ProjectStatus
from seehere.db.models import Job, Project
from seehere.jobs import queue
from seehere.jobs.errors import PermanentJobError
from seehere.jobs.queue import ClaimedJob
from seehere.jobs.worker import JobContext, Worker

Sessions = sessionmaker[Session]


def _settings(tmp_path: Path, **kw: float) -> Settings:
    values: dict = {
        "media_dir": tmp_path / "media",
        "job_heartbeat_interval_s": 0.1,
        "job_stale_after_s": 1.0,
        "job_retry_base_s": 10.0,
        "job_retry_max_s": 300.0,
        "worker_poll_interval_s": 0.05,
    }
    values.update(kw)
    return Settings(**values)


def _project(sessions: Sessions, **kw: object) -> uuid.UUID:
    with sessions() as s:
        p = Project(title="Lecture", rights_confirmed_at=datetime.now(UTC), **kw)
        s.add(p)
        s.commit()
        return p.id


def _enqueue(
    sessions: Sessions, project_id: uuid.UUID, kind: str = "test.ok", **kw: object
) -> uuid.UUID:
    with sessions() as s:
        job = queue.enqueue(
            s,
            project_id=project_id,
            kind=kind,
            idempotency_key=f"{kind}:{uuid.uuid4()}",
            **kw,  # type: ignore[arg-type]
        )
        s.commit()
        return job.id


def _job(sessions: Sessions, job_id: uuid.UUID) -> Job:
    with sessions() as s:
        job = s.get(Job, job_id)
        assert job is not None
        return job


def _project_status(sessions: Sessions, project_id: uuid.UUID) -> ProjectStatus:
    with sessions() as s:
        return s.scalars(select(Project.status).where(Project.id == project_id)).one()


# --- queue operations -------------------------------------------------------------------------


def test_enqueue_is_idempotent(sessions: Sessions) -> None:
    pid = _project(sessions)
    with sessions() as s:
        a = queue.enqueue(s, project_id=pid, kind="test.ok", idempotency_key="same")
        b = queue.enqueue(s, project_id=pid, kind="test.ok", idempotency_key="same")
        s.commit()
        assert a.id == b.id
        assert s.scalar(select(func.count()).select_from(Job)) == 1


def test_claim_takes_runnable_jobs_of_known_kinds_only(sessions: Sessions) -> None:
    pid = _project(sessions)
    ok = _enqueue(sessions, pid)
    _enqueue(sessions, pid, kind="test.other")
    later = _enqueue(sessions, pid)
    with sessions() as s:
        s.execute(
            update(Job).where(Job.id == later).values(run_after=func.now() + timedelta(hours=1))
        )
        s.commit()
        job = queue.claim(s, "w1", ["test.ok"])
        assert job is not None and job.id == ok and job.attempts == 1
        assert queue.claim(s, "w2", ["test.ok"]) is None
    row = _job(sessions, ok)
    assert (row.status, row.locked_by, row.attempts) == (JobStatus.RUNNING, "w1", 1)
    assert row.heartbeat_at is not None


def test_claim_skips_a_row_another_transaction_has_locked(sessions: Sessions) -> None:
    pid = _project(sessions)
    first = _enqueue(sessions, pid)
    second = _enqueue(sessions, pid)
    holder = sessions()
    try:
        # Another worker is mid-claim on the first job: its row lock is held, uncommitted.
        holder.execute(text("SELECT id FROM job WHERE id = :id FOR UPDATE"), {"id": first})
        with sessions() as s:
            job = queue.claim(s, "w2", ["test.ok"])
        assert job is not None and job.id == second
    finally:
        holder.rollback()
        holder.close()


def test_concurrent_workers_never_claim_the_same_job(sessions: Sessions) -> None:
    pid = _project(sessions)
    ids = {_enqueue(sessions, pid) for _ in range(40)}
    claimed: list[uuid.UUID] = []
    lock = threading.Lock()
    start = threading.Barrier(8)

    def worker(n: int) -> None:
        start.wait()
        while True:
            with sessions() as s:
                job = queue.claim(s, f"w{n}", ["test.ok"])
            if job is None:
                return
            with lock:
                claimed.append(job.id)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert len(claimed) == 40
    assert set(claimed) == ids


def test_only_the_lease_holder_can_update_a_job(sessions: Sessions) -> None:
    pid = _project(sessions)
    job_id = _enqueue(sessions, pid)
    with sessions() as s:
        job = queue.claim(s, "owner", ["test.ok"])
        assert job is not None
        assert queue.heartbeat(s, job_id, "intruder") is None
        assert queue.report_progress(s, job_id, "intruder", "x", 0.5) is None
        assert queue.complete(s, job_id, "intruder") is False
        assert queue.mark_cancelled(s, job_id, "intruder") is False
        assert queue.heartbeat(s, job_id, "owner") is False
        assert queue.report_progress(s, job_id, "owner", "audio", 1.7) is False
    row = _job(sessions, job_id)
    assert (row.status, row.stage, row.progress) == (JobStatus.RUNNING, "audio", 1.0)


@pytest.mark.parametrize(("attempt", "delay"), [(1, 10), (2, 20), (3, 40), (6, 300), (20, 300)])
def test_retry_delay_is_exponential_and_capped(attempt: int, delay: float) -> None:
    assert queue.retry_delay_s(attempt, 10, 300) == delay


def test_retryable_failures_back_off_then_fail_when_attempts_run_out(sessions: Sessions) -> None:
    pid = _project(sessions)
    job_id = _enqueue(sessions, pid, max_attempts=2)
    with sessions() as s:
        job = queue.claim(s, "w", ["test.ok"])
        assert job is not None
        status = queue.fail(s, job, "w", "boom", retryable=True, base_s=10, max_s=300)
        assert status is JobStatus.QUEUED
        delay = s.scalar(select(Job.run_after - func.now()).where(Job.id == job_id))
        assert delay is not None and timedelta(seconds=9) < delay <= timedelta(seconds=10)
        assert queue.claim(s, "w", ["test.ok"]) is None  # not runnable yet
        s.execute(update(Job).where(Job.id == job_id).values(run_after=func.now()))
        s.commit()
        job = queue.claim(s, "w", ["test.ok"])
        assert job is not None and job.attempts == 2
        status = queue.fail(s, job, "w", "boom again", retryable=True, base_s=10, max_s=300)
        assert status is JobStatus.FAILED
    row = _job(sessions, job_id)
    assert (row.status, row.error, row.attempts) == (JobStatus.FAILED, "boom again", 2)
    assert row.finished_at is not None and row.locked_by is None


def test_permanent_failures_are_not_retried(sessions: Sessions) -> None:
    pid = _project(sessions)
    job_id = _enqueue(sessions, pid, max_attempts=5)
    with sessions() as s:
        job = queue.claim(s, "w", ["test.ok"])
        assert job is not None
        assert (
            queue.fail(s, job, "w", "corrupt", retryable=False, base_s=1, max_s=1)
            is JobStatus.FAILED
        )
    assert _job(sessions, job_id).attempts == 1


def test_cancel_queued_is_immediate_and_running_is_requested(sessions: Sessions) -> None:
    pid = _project(sessions)
    queued = _enqueue(sessions, pid)
    running = _enqueue(sessions, pid)
    with sessions() as s:
        s.execute(
            update(Job).where(Job.id == queued).values(run_after=func.now() + timedelta(hours=1))
        )
        s.commit()
        assert queue.claim(s, "w", ["test.ok"]) is not None
        a = queue.request_cancel(s, queued)
        b = queue.request_cancel(s, running)
        assert a is not None and a.status is JobStatus.CANCELLED and a.finished_at is not None
        assert b is not None and b.status is JobStatus.RUNNING and b.cancel_requested
        assert queue.heartbeat(s, running, "w") is True
        assert queue.request_cancel(s, uuid.uuid4()) is None


def test_retry_requeues_only_finished_unsuccessful_jobs(sessions: Sessions) -> None:
    pid = _project(sessions)
    job_id = _enqueue(sessions, pid)
    with sessions() as s:
        assert queue.retry(s, job_id) is None  # still queued
        job = queue.claim(s, "w", ["test.ok"])
        assert job is not None
        queue.fail(s, job, "w", "bad", retryable=False, base_s=1, max_s=1)
        again = queue.retry(s, job_id)
        assert again is not None
        assert (again.status, again.attempts, again.error, again.finished_at) == (
            JobStatus.QUEUED,
            0,
            None,
            None,
        )


def test_recover_stale_requeues_fails_or_cancels(sessions: Sessions) -> None:
    pid = _project(sessions)
    requeue = _enqueue(sessions, pid, max_attempts=3)
    exhausted = _enqueue(sessions, pid, max_attempts=1)
    cancelled = _enqueue(sessions, pid, max_attempts=3)
    fresh = _enqueue(sessions, pid, max_attempts=3)
    with sessions() as s:
        for _ in range(4):
            assert queue.claim(s, "dead", ["test.ok"]) is not None
        s.execute(update(Job).where(Job.id == cancelled).values(cancel_requested=True))
        s.execute(
            update(Job)
            .where(Job.id.in_([requeue, exhausted, cancelled]))
            .values(heartbeat_at=func.now() - timedelta(minutes=5))
        )
        s.commit()
        recovered = queue.recover_stale(s, stale_after_s=60)
    assert set(recovered) == {requeue, exhausted, cancelled}
    assert _job(sessions, requeue).status is JobStatus.QUEUED
    assert _job(sessions, requeue).error == queue.STALE_MESSAGE
    assert _job(sessions, exhausted).status is JobStatus.FAILED
    assert _job(sessions, cancelled).status is JobStatus.CANCELLED
    assert _job(sessions, fresh).status is JobStatus.RUNNING


def test_project_status_follows_its_jobs(sessions: Sessions) -> None:
    pid = _project(sessions)
    with sessions() as s:
        queue.refresh_project_status(s, pid)
    assert _project_status(sessions, pid) is ProjectStatus.UPLOADED
    job_id = _enqueue(sessions, pid)
    with sessions() as s:
        queue.refresh_project_status(s, pid)
    assert _project_status(sessions, pid) is ProjectStatus.PROCESSING
    with sessions() as s:
        job = queue.claim(s, "w", ["test.ok"])
        assert job is not None
        queue.fail(s, job, "w", "x", retryable=False, base_s=1, max_s=1)
        queue.refresh_project_status(s, pid)
    assert _project_status(sessions, pid) is ProjectStatus.FAILED
    with sessions() as s:
        queue.retry(s, job_id)
        queue.refresh_project_status(s, pid)
    assert _project_status(sessions, pid) is ProjectStatus.PROCESSING
    with sessions() as s:  # the export (the last stage) succeeds: ready
        s.execute(
            update(Job).where(Job.id == job_id).values(kind="export.build", status="succeeded")
        )
        s.commit()
        queue.refresh_project_status(s, pid)
    assert _project_status(sessions, pid) is ProjectStatus.READY
    _enqueue(sessions, pid)  # new work (for example after a review): processing again
    with sessions() as s:
        queue.refresh_project_status(s, pid)
    assert _project_status(sessions, pid) is ProjectStatus.PROCESSING


# --- worker ----------------------------------------------------------------------------------


def _worker(
    sessions: Sessions,
    tmp_path: Path,
    handler: Callable[[JobContext, ClaimedJob], None],
    **kw: float,
) -> Worker:
    return Worker({"test.ok": handler}, settings=_settings(tmp_path, **kw), sessions=sessions)


def test_worker_runs_a_job_and_records_progress(sessions: Sessions, tmp_path: Path) -> None:
    seen: list[float] = []

    def handler(ctx: JobContext, job: ClaimedJob) -> None:
        for i in range(3):
            ctx.progress("step", i / 3)
            with sessions() as s:
                seen.append(s.scalar(select(Job.progress).where(Job.id == job.id)) or 0)
            time.sleep(0.3)

    pid = _project(sessions)
    job_id = _enqueue(sessions, pid)
    worker = _worker(sessions, tmp_path, handler)
    assert worker.run_once() is True
    assert worker.run_once() is False
    assert seen == pytest.approx([0, 1 / 3, 2 / 3])
    row = _job(sessions, job_id)
    assert (row.status, row.progress, row.stage, row.locked_by) == (
        JobStatus.SUCCEEDED,
        1.0,
        "step",
        None,
    )
    assert _project_status(sessions, pid) is ProjectStatus.UPLOADED


def test_worker_retries_unexpected_errors_with_a_safe_message(
    sessions: Sessions, tmp_path: Path
) -> None:
    calls = 0

    def flaky(ctx: JobContext, job: ClaimedJob) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("/secret/path/leaked in a traceback")

    pid = _project(sessions)
    job_id = _enqueue(sessions, pid)
    worker = _worker(sessions, tmp_path, flaky)
    worker.run_once()
    row = _job(sessions, job_id)
    assert row.status is JobStatus.QUEUED
    assert row.error == "An unexpected error stopped this step."
    assert _project_status(sessions, pid) is ProjectStatus.PROCESSING
    with sessions() as s:
        s.execute(update(Job).where(Job.id == job_id).values(run_after=func.now()))
        s.commit()
    worker.run_once()
    row = _job(sessions, job_id)
    assert (row.status, row.attempts, row.error) == (JobStatus.SUCCEEDED, 2, None)


def test_worker_fails_permanent_errors_and_the_project(sessions: Sessions, tmp_path: Path) -> None:
    def handler(ctx: JobContext, job: ClaimedJob) -> None:
        raise PermanentJobError("The video could not be decoded.")

    pid = _project(sessions)
    job_id = _enqueue(sessions, pid)
    _worker(sessions, tmp_path, handler).run_once()
    row = _job(sessions, job_id)
    assert (row.status, row.attempts, row.error) == (
        JobStatus.FAILED,
        1,
        "The video could not be decoded.",
    )
    assert _project_status(sessions, pid) is ProjectStatus.FAILED


def test_worker_stops_a_running_job_when_cancel_is_requested(
    sessions: Sessions, tmp_path: Path
) -> None:
    started = threading.Event()
    steps = 0

    def slow(ctx: JobContext, job: ClaimedJob) -> None:
        nonlocal steps
        started.set()
        while steps < 200:  # would take 10 s without cancellation
            steps += 1
            ctx.check_cancelled()
            time.sleep(0.05)

    pid = _project(sessions)
    job_id = _enqueue(sessions, pid)
    worker = _worker(sessions, tmp_path, slow)
    t = threading.Thread(target=worker.run_once)
    t.start()
    assert started.wait(5)
    with sessions() as s:
        queue.request_cancel(s, job_id)
    t.join(timeout=5)
    assert not t.is_alive()
    row = _job(sessions, job_id)
    assert row.status is JobStatus.CANCELLED and steps < 200
    assert _project_status(sessions, pid) is ProjectStatus.UPLOADED


def test_worker_that_lost_its_lease_does_not_overwrite_the_job(
    sessions: Sessions, tmp_path: Path
) -> None:
    def handler(ctx: JobContext, job: ClaimedJob) -> None:
        with sessions() as s:  # meanwhile, the job was recovered and claimed by someone else
            s.execute(update(Job).where(Job.id == job.id).values(locked_by="other-worker"))
            s.commit()
        time.sleep(0.3)  # the heartbeat notices the lost lease
        ctx.check_cancelled()

    pid = _project(sessions)
    job_id = _enqueue(sessions, pid)
    _worker(sessions, tmp_path, handler).run_once()
    row = _job(sessions, job_id)
    assert (row.status, row.locked_by) == (JobStatus.RUNNING, "other-worker")


def test_worker_loop_stops_cleanly(sessions: Sessions, tmp_path: Path) -> None:
    ran = threading.Event()
    pid = _project(sessions)
    _enqueue(sessions, pid)
    worker = _worker(sessions, tmp_path, lambda ctx, job: ran.set())
    t = threading.Thread(target=worker.run)
    t.start()
    assert ran.wait(5)
    worker.stop_event.set()
    t.join(timeout=5)
    assert not t.is_alive()


CRASHING_WORKER = textwrap.dedent(
    """
    import sys, time
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from seehere.core.config import Settings
    from seehere.jobs.worker import Worker

    def hang(ctx, job):
        print("running", flush=True)
        time.sleep(60)

    sessions = sessionmaker(bind=create_engine(sys.argv[1]), expire_on_commit=False)
    settings = Settings(media_dir=sys.argv[2], job_heartbeat_interval_s=0.1)
    Worker({"test.ok": hang}, settings=settings, sessions=sessions, worker_id="doomed").run_once()
    """
)


def test_job_of_a_killed_worker_process_is_recovered_and_finished(
    sessions: Sessions, migrated_engine: Engine, tmp_path: Path
) -> None:
    pid = _project(sessions)
    job_id = _enqueue(sessions, pid)
    url = migrated_engine.url.render_as_string(hide_password=False)
    proc = subprocess.Popen(  # noqa: S603 - fixed argv
        [sys.executable, "-c", CRASHING_WORKER, url, str(tmp_path / "media")],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert proc.stdout is not None and proc.stdout.readline().strip() == "running"
        assert _job(sessions, job_id).locked_by == "doomed"
        os.kill(proc.pid, signal.SIGKILL)  # no cleanup code runs: a real crash
        proc.wait(timeout=10)
    finally:
        if proc.poll() is None:
            proc.kill()

    worker = _worker(sessions, tmp_path, lambda ctx, job: None, job_stale_after_s=1.0)
    worker.maintenance()
    assert _job(sessions, job_id).status is JobStatus.RUNNING  # heartbeat still fresh
    time.sleep(1.5)
    worker.maintenance()
    row = _job(sessions, job_id)
    assert (row.status, row.error) == (JobStatus.QUEUED, queue.STALE_MESSAGE)
    assert worker.run_once() is True
    row = _job(sessions, job_id)
    assert (row.status, row.attempts) == (JobStatus.SUCCEEDED, 2)
