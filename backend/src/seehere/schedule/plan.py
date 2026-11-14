"""The scheduling job: speech windows from the transcript, a greedy standard-mode schedule of
the verified cues, an independent validation, and a stored run (`schedule_run`).

Cues still marked needs_review are held back: nothing unverified is voiced until a person
approves it (Task 26). A schedule that fails validation is stored as failed, never used.
"""

from __future__ import annotations

import logging
import time
import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from seehere.db.enums import (
    DescriptionMode,
    DescriptionVariant,
    MediaKind,
    ReviewStatus,
    ScheduleStatus,
    SolverKind,
    VerificationState,
)
from seehere.db.models import (
    DescriptionCue,
    MediaAsset,
    SchedulePlacement,
    ScheduleRun,
    TranscriptWord,
    VisualUnit,
)
from seehere.jobs import queue
from seehere.jobs.errors import PermanentJobError
from seehere.jobs.queue import ClaimedJob
from seehere.jobs.worker import JobContext
from seehere.schedule.greedy import CueInput, schedule_greedy, validate
from seehere.schedule.windows import estimate_duration_s, speech_windows

log = logging.getLogger("seehere.schedule")

JOB_KIND = "schedule.greedy"
NO_UNIT_SPAN_S = 10.0  # a cue without a visual unit may play this long after its anchor


def queue_schedule(session: Session, project_id: uuid.UUID) -> None:
    """Queue (or re-queue) after verification. Does not commit."""
    queue.enqueue_or_restart(
        session, project_id=project_id, kind=JOB_KIND, idempotency_key=f"{JOB_KIND}:{project_id}"
    )


def plan_schedule(ctx: JobContext, job: ClaimedJob) -> None:
    cfg = ctx.settings
    pid = job.project_id
    with ctx.session() as s:
        audio = s.scalars(
            select(MediaAsset).where(
                MediaAsset.project_id == pid, MediaAsset.kind == MediaKind.NORMALIZED_AUDIO
            )
        ).first()
        if audio is None or not audio.duration_s:
            raise PermanentJobError("The prepared audio is missing. Run media preparation again.")
        words = [
            (w.start_s, w.end_s)
            for w in s.execute(
                select(TranscriptWord.start_s, TranscriptWord.end_s)
                .where(TranscriptWord.media_asset_id == audio.id)
                .order_by(TranscriptWord.idx)
            )
        ]
        windows = speech_windows(
            words, audio.duration_s, pad_s=cfg.window_pad_s, min_length_s=cfg.window_min_s
        )
        rows = list(
            s.execute(
                select(DescriptionCue, VisualUnit.t_end_s)
                .outerjoin(VisualUnit, DescriptionCue.visual_unit_id == VisualUnit.id)
                .where(
                    DescriptionCue.project_id == pid,
                    DescriptionCue.review_status != ReviewStatus.REJECTED,
                )
            )
        )
        held = [c for c, _ in rows if c.verification_state is VerificationState.NEEDS_REVIEW]
        inputs = [
            CueInput(
                id=c.id,
                priority=c.priority,
                earliest_s=c.anchor_t_s,
                latest_s=(unit_end if unit_end is not None else c.anchor_t_s + NO_UNIT_SPAN_S)
                + cfg.schedule_grace_s,
                durations={
                    variant: estimate_duration_s(text, cfg.description_words_per_s)
                    for variant, text in (
                        (DescriptionVariant.SHORT, c.text_short),
                        (DescriptionVariant.MEDIUM, c.text_medium),
                        (DescriptionVariant.LONG, c.text_long),
                    )
                    if text
                },
            )
            for c, unit_end in rows
            if c.verification_state is not VerificationState.NEEDS_REVIEW
        ]

        ctx.progress("schedule", 0.5)
        began = time.perf_counter()
        placed, skipped = schedule_greedy(inputs, windows)
        problems = validate(placed, windows)
        elapsed_ms = (time.perf_counter() - began) * 1000

        total_priority = sum(c.priority for c in inputs)
        placed_priority = sum(c.priority for c in inputs if c.id in {p.cue_id for p in placed})
        run = ScheduleRun(
            project_id=pid,
            solver=SolverKind.GREEDY,
            mode=DescriptionMode.STANDARD,
            status=ScheduleStatus.FAILED if problems else ScheduleStatus.SUCCEEDED,
            params={
                "window_pad_s": cfg.window_pad_s,
                "window_min_s": cfg.window_min_s,
                "grace_s": cfg.schedule_grace_s,
                "words_per_s": cfg.description_words_per_s,
            },
            metrics={
                "windows": [[w.start_s, w.end_s] for w in windows],
                "window_total_s": round(sum(w.length for w in windows), 3),
                "considered": len(inputs),
                "placed": len(placed),
                "skipped": [{"cue_id": str(k.cue_id), "reason": k.reason} for k in skipped],
                "held_for_review": [str(c.id) for c in held],
                "priority_placed_share": round(placed_priority / total_priority, 4)
                if total_priority
                else None,
                "described_s": round(sum(p.end_s - p.start_s for p in placed), 3),
                "speech_overlap_s": 0.0 if not problems else None,
                "violations": problems,
            },
            duration_ms=round(elapsed_ms, 3),
        )
        ctx.check_cancelled()
        s.execute(
            delete(ScheduleRun).where(
                ScheduleRun.project_id == pid,
                ScheduleRun.solver == SolverKind.GREEDY,
                ScheduleRun.mode == DescriptionMode.STANDARD,
            )
        )
        s.add(run)
        s.flush()
        if not problems:
            s.add_all(
                SchedulePlacement(
                    run_id=run.id,
                    cue_id=p.cue_id,
                    variant=p.variant,
                    start_s=p.start_s,
                    end_s=p.end_s,
                )
                for p in placed
            )
        s.commit()
    if problems:
        log.error("project %s: greedy schedule invalid: %s", pid, problems)
        raise PermanentJobError("The schedule failed its overlap check and was not used.")
    log.info(
        "project %s: %d placed, %d skipped, %d held for review, %d windows",
        pid,
        len(placed),
        len(skipped),
        len(held),
        len(windows),
    )
    ctx.progress("schedule", 1.0)
