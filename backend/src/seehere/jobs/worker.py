"""The worker process: claims jobs, runs their handlers and records the outcome.

Run it with `make worker` (or `uv run python -m seehere.jobs.worker`). Several workers may run at
once; each job goes to exactly one of them at a time. While a handler runs, a heartbeat thread
refreshes the job's lease every `job_heartbeat_interval_s` and watches for cancel requests.
SIGINT/SIGTERM stop the loop after the current job; a hard kill is recovered by `recover_stale`.
"""

from __future__ import annotations

import logging
import os
import signal
import socket
import threading
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import FrameType

from sqlalchemy.orm import Session, sessionmaker

from seehere.core.config import Settings, get_settings
from seehere.db.session import get_sessionmaker
from seehere.jobs import queue
from seehere.jobs.errors import JobCancelled, PermanentJobError
from seehere.jobs.queue import ClaimedJob
from seehere.jobs.retention import sweep
from seehere.media.storage import MediaStore

log = logging.getLogger("seehere.worker")

Handler = Callable[["JobContext", ClaimedJob], None]


@dataclass
class JobContext:
    """What a handler may use: settings, storage, sessions, progress and cancellation."""

    job: ClaimedJob
    worker_id: str
    settings: Settings
    store: MediaStore
    sessions: sessionmaker[Session]
    cancel_event: threading.Event = field(default_factory=threading.Event)
    _last_write: float = 0.0
    _last_stage: str | None = None

    def session(self) -> Session:
        return self.sessions()

    def check_cancelled(self) -> None:
        if self.cancel_event.is_set():
            raise JobCancelled

    def progress(self, stage: str, fraction: float) -> None:
        """Report progress (0..1) for a named stage. Writes are throttled to 4 per second,
        except stage changes and completion. Raises JobCancelled if cancellation was requested."""
        now = time.monotonic()
        if stage == self._last_stage and fraction < 1 and now - self._last_write < 0.25:
            self.check_cancelled()
            return
        self._last_write, self._last_stage = now, stage
        with self.session() as s:
            cancel = queue.report_progress(s, self.job.id, self.worker_id, stage, fraction)
        if cancel is None or cancel:
            self.cancel_event.set()
        self.check_cancelled()


class _Heartbeat(threading.Thread):
    def __init__(self, ctx: JobContext, interval_s: float) -> None:
        super().__init__(name=f"heartbeat-{ctx.job.id}", daemon=True)
        self.ctx, self.interval_s = ctx, interval_s
        self.stopped = threading.Event()

    def run(self) -> None:
        while not self.stopped.wait(self.interval_s):
            try:
                with self.ctx.session() as s:
                    cancel = queue.heartbeat(s, self.ctx.job.id, self.ctx.worker_id)
            except Exception:  # a DB blip must not kill the job; the next beat retries
                log.warning("heartbeat failed for job %s", self.ctx.job.id, exc_info=True)
                continue
            if cancel is None or cancel:
                self.ctx.cancel_event.set()


class Worker:
    def __init__(
        self,
        handlers: Mapping[str, Handler],
        *,
        settings: Settings | None = None,
        sessions: sessionmaker[Session] | None = None,
        worker_id: str | None = None,
    ) -> None:
        self.handlers = dict(handlers)
        self.settings = settings or get_settings()
        self.sessions = sessions or get_sessionmaker()
        self.store = MediaStore(self.settings.media_dir)
        self.worker_id = worker_id or f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:6]}"
        self.stop_event = threading.Event()
        self._last_maintenance = float("-inf")

    def run_once(self) -> bool:
        """Claim and run one job. Returns False if there was nothing to do."""
        with self.sessions() as s:
            job = queue.claim(s, self.worker_id, sorted(self.handlers))
        if job is None:
            return False
        self._execute(job)
        return True

    def _execute(self, job: ClaimedJob) -> None:
        cfg = self.settings
        ctx = JobContext(job, self.worker_id, cfg, self.store, self.sessions)
        beat = _Heartbeat(ctx, cfg.job_heartbeat_interval_s)
        beat.start()
        log.info("job %s (%s) started, attempt %d", job.id, job.kind, job.attempts)
        try:
            with self.sessions() as s:
                queue.refresh_project_status(s, job.project_id)
            self.handlers[job.kind](ctx, job)
        except JobCancelled:
            with self.sessions() as s:
                queue.mark_cancelled(s, job.id, self.worker_id)
            log.info("job %s cancelled", job.id)
        except PermanentJobError as exc:
            with self.sessions() as s:
                queue.fail(
                    s,
                    job,
                    self.worker_id,
                    exc.message,
                    retryable=False,
                    base_s=cfg.job_retry_base_s,
                    max_s=cfg.job_retry_max_s,
                )
            log.warning("job %s failed permanently: %s", job.id, exc.message)
        except Exception:
            # Unknown errors are logged in full here but shown to users only generically.
            log.exception("job %s raised", job.id)
            with self.sessions() as s:
                status = queue.fail(
                    s,
                    job,
                    self.worker_id,
                    "An unexpected error stopped this step.",
                    retryable=True,
                    base_s=cfg.job_retry_base_s,
                    max_s=cfg.job_retry_max_s,
                )
            log.info("job %s is now %s", job.id, status)
        else:
            with self.sessions() as s:
                done = queue.complete(s, job.id, self.worker_id)
            log.info(
                "job %s %s", job.id, "succeeded" if done else "finished after losing its lease"
            )
        finally:
            beat.stopped.set()
            beat.join()
            with self.sessions() as s:
                queue.refresh_project_status(s, job.project_id)

    def maintenance(self) -> None:
        """Recover abandoned jobs and delete expired projects. Safe to run on every worker."""
        with self.sessions() as s:
            for job_id in queue.recover_stale(s, self.settings.job_stale_after_s):
                log.warning("recovered stale job %s", job_id)
        with self.sessions() as s:
            sweep(s, self.store, self.settings)

    def run(self) -> None:
        log.info("worker %s handling %s", self.worker_id, ", ".join(sorted(self.handlers)))
        while not self.stop_event.is_set():
            now = time.monotonic()
            if now - self._last_maintenance >= self.settings.retention_sweep_interval_s:
                self._last_maintenance = now
                try:
                    self.maintenance()
                except Exception:
                    log.exception("maintenance failed")
            try:
                worked = self.run_once()
            except Exception:  # e.g. database unavailable: wait and try again
                log.exception("could not claim a job")
                worked = False
            if not worked:
                self.stop_event.wait(self.settings.worker_poll_interval_s)
        log.info("worker %s stopped", self.worker_id)


def main() -> None:
    from seehere.pipeline import HANDLERS

    logging.basicConfig(
        level=get_settings().log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    worker = Worker(HANDLERS)

    def stop(signum: int, _frame: FrameType | None) -> None:
        log.info("signal %d: finishing the current job, then stopping", signum)
        worker.stop_event.set()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    worker.run()


if __name__ == "__main__":
    main()
