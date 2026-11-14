"""Post-synthesis timing validation (Task 23).

Schedules are first built from estimated speaking times. Once the voice exists, every placement
is checked against its clip's measured length. If any clip is longer than its slot (or has no
audio), the schedules are rebuilt with the measured lengths (`build_schedules` prefers them)
and the new wordings are synthesized: at most `MAX_ROUNDS` rounds in all. In the last round,
placements that still do not fit are removed, with the reason recorded in the run and logged.

When everything fits, each run records `timing.status = "fits"` and export is queued.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from seehere.db.enums import ScheduleStatus
from seehere.db.models import AudioClip, DescriptionCue, SchedulePlacement, ScheduleRun
from seehere.jobs import queue
from seehere.jobs.errors import PermanentJobError
from seehere.jobs.queue import ClaimedJob
from seehere.jobs.worker import JobContext

log = logging.getLogger("seehere.timing")

JOB_KIND = "timing.check"
MAX_ROUNDS = 3
TOLERANCE_S = 0.001  # clip lengths are whole milliseconds


def queue_timing_check(session: Session, project_id: uuid.UUID) -> None:
    """Queue (or re-queue) after speech synthesis. Does not commit."""
    queue.enqueue_or_restart(
        session, project_id=project_id, kind=JOB_KIND, idempotency_key=f"{JOB_KIND}:{project_id}"
    )


def misfit(slot_s: float, audio_s: float | None) -> str | None:
    """Why a clip does not fit its slot, or None if it does."""
    if audio_s is None:
        return "no audio was generated for it"
    if audio_s > slot_s + TOLERANCE_S:
        return f"its spoken audio ({audio_s:.2f} s) is longer than its slot ({slot_s:.2f} s)"
    return None


def check_timing(ctx: JobContext, job: ClaimedJob) -> None:
    # The pipeline loops plan -> synthesize -> timing -> plan, so these import at call time.
    from seehere.export.build import queue_export
    from seehere.schedule.plan import build_schedules
    from seehere.speech.synthesize import queue_synthesis

    pid = job.project_id
    with ctx.session() as s:
        runs = list(
            s.scalars(
                select(ScheduleRun).where(
                    ScheduleRun.project_id == pid,
                    ScheduleRun.status == ScheduleStatus.SUCCEEDED,
                )
            )
        )
        if not runs:
            raise PermanentJobError("There is no schedule to check. Run scheduling again.")
        round_no = max(r.round for r in runs)
        clips = {
            (a.cue_id, a.variant): a.duration_s
            for a in s.scalars(
                select(AudioClip).join(DescriptionCue).where(DescriptionCue.project_id == pid)
            )
        }
        bad: dict[uuid.UUID, list[tuple[SchedulePlacement, str]]] = {}
        checked = 0
        for run in runs:
            for p in s.scalars(select(SchedulePlacement).where(SchedulePlacement.run_id == run.id)):
                checked += 1
                why = misfit(p.end_s - p.start_s, clips.get((p.cue_id, p.variant)))
                if why:
                    bad.setdefault(run.id, []).append((p, why))

        if bad and round_no < MAX_ROUNDS:
            ctx.progress("timing", 0.5)
            ok = build_schedules(
                s,
                ctx.settings,
                pid,
                progress=ctx.progress,
                check=ctx.check_cancelled,
                round_no=round_no + 1,
            )
            if not ok:
                s.rollback()
                raise PermanentJobError("Re-scheduling with measured lengths failed validation.")
            queue_synthesis(s, pid)
            s.commit()
            log.info(
                "project %s: %d placement(s) did not fit in round %d; re-solving",
                pid,
                sum(len(v) for v in bad.values()),
                round_no,
            )
            return

        for run in runs:
            rejected = bad.get(run.id, [])
            for p, why in rejected:
                s.delete(p)
                log.warning(
                    "project %s: cue %s rejected after timing check: %s", pid, p.cue_id, why
                )
            metrics: dict[str, Any] = dict(run.metrics)
            metrics["skipped"] = [
                *metrics.get("skipped", []),
                *(
                    {"cue_id": str(p.cue_id), "reason": f"{why} after {round_no} rounds"}
                    for p, why in rejected
                ),
            ]
            metrics["placed"] = metrics.get("placed", 0) - len(rejected)
            if "paused_s" in metrics:
                metrics["paused_s"] = round(
                    metrics["paused_s"] - sum(p.inserted_pause_s for p, _ in rejected), 3
                )
            metrics["timing"] = {
                "status": "fits",
                "round": round_no,
                "rejected": len(rejected),
            }
            run.metrics = metrics
        queue_export(s, pid)
        s.commit()
    log.info("project %s: timing checked in round %d, %d placements", pid, round_no, checked)
    ctx.progress("timing", 1.0)
