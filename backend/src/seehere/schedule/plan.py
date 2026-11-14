"""The scheduling job: speech windows from the transcript; greedy and CP-SAT standard-mode
schedules of the verified cues on identical inputs (ADR-007); the extended plan built on the
better of the two; independent validation of each; one stored `schedule_run` per result.

Cues still marked needs_review are held back: nothing unverified is voiced until a person
approves it (Task 26). A schedule that fails validation is stored as failed, never used.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

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
from seehere.schedule.cp_sat import schedule_cp_sat
from seehere.schedule.extended import plan_extended, validate_extended
from seehere.schedule.greedy import CueInput, Placement, Skipped, schedule_greedy, validate
from seehere.schedule.windows import estimate_duration_s, speech_windows
from seehere.speech.synthesize import queue_synthesis

log = logging.getLogger("seehere.schedule")

JOB_KIND = "schedule.plan"
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
                select(DescriptionCue, VisualUnit.t_end_s, VisualUnit.label)
                .outerjoin(VisualUnit, DescriptionCue.visual_unit_id == VisualUnit.id)
                .where(
                    DescriptionCue.project_id == pid,
                    DescriptionCue.review_status != ReviewStatus.REJECTED,
                )
            )
        )
        held = [c for c, _, _ in rows if c.verification_state is VerificationState.NEEDS_REVIEW]
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
            for c, unit_end, _ in rows
            if c.verification_state is not VerificationState.NEEDS_REVIEW
        ]

        labels = {c.id: (label or "This visual") for c, _, label in rows}
        held_ids = [str(c.id) for c in held]
        params = {
            "window_pad_s": cfg.window_pad_s,
            "window_min_s": cfg.window_min_s,
            "grace_s": cfg.schedule_grace_s,
            "words_per_s": cfg.description_words_per_s,
        }
        common = {
            "windows": [[w.start_s, w.end_s] for w in windows],
            "window_total_s": round(sum(w.length for w in windows), 3),
            "considered": len(inputs),
            "held_for_review": held_ids,
        }

        ctx.progress("schedule", 0.3)
        began = time.perf_counter()
        greedy_placed, greedy_skipped = schedule_greedy(inputs, windows)
        greedy_ms = (time.perf_counter() - began) * 1000
        ctx.progress("schedule", 0.5)
        began = time.perf_counter()
        cp = schedule_cp_sat(inputs, windows, time_limit_s=cfg.solver_time_limit_s)
        cp_ms = (time.perf_counter() - began) * 1000

        def metrics(placed: list[Placement], skipped: list[Skipped]) -> dict[str, Any]:
            problems = validate(placed, windows)
            total = sum(c.priority for c in inputs)
            got = sum(c.priority for c in inputs if c.id in {p.cue_id for p in placed})
            return {
                **common,
                "placed": len(placed),
                "skipped": [{"cue_id": str(k.cue_id), "reason": k.reason} for k in skipped],
                "priority_placed_share": round(got / total, 4) if total else None,
                "described_s": round(sum(p.end_s - p.start_s for p in placed), 3),
                "speech_overlap_s": 0.0 if not problems else None,
                "violations": problems,
            }

        g_m, c_m = metrics(greedy_placed, greedy_skipped), metrics(cp.placed, cp.skipped)
        c_m["solver_status"] = cp.status
        cp_ok = cp.status != "no_solution" and not c_m["violations"]
        g_ok = not g_m["violations"]
        # CP-SAT is kept only when it is at least as good (ADR-007); ties go to CP-SAT, whose
        # objective also prefers longer wordings and earlier starts.
        use_cp = cp_ok and (
            not g_ok or (c_m["priority_placed_share"] or 0) >= (g_m["priority_placed_share"] or 0)
        )
        g_m["selected"], c_m["selected"] = not use_cp and g_ok, use_cp
        comparison = {
            "greedy": {k: g_m[k] for k in ("placed", "priority_placed_share", "described_s")}
            | {"duration_ms": round(greedy_ms, 3)},
            "cp_sat": {k: c_m[k] for k in ("placed", "priority_placed_share", "described_s")}
            | {"duration_ms": round(cp_ms, 3), "status": cp.status},
        }
        g_m["comparison"] = c_m["comparison"] = comparison

        ctx.progress("schedule", 0.8)
        base = cp.placed if use_cp else greedy_placed
        ext = plan_extended(
            base if (use_cp or g_ok) else [],
            inputs,
            words,
            audio.duration_s,
            pad_s=cfg.window_pad_s,
            budget_pct=cfg.extended_pause_budget_pct,
            labels=labels,
        )
        e_problems = validate_extended(ext, words)
        e_m = {
            **common,
            "placed": len(ext.placements),
            "paused": len(ext.pauses),
            "skipped": [{"cue_id": str(c), "reason": r} for c, r in ext.skipped],
            "budget_s": ext.budget_s,
            "paused_s": ext.paused_s,
            "extended_duration_s": round(audio.duration_s + ext.paused_s, 3),
            "violations": e_problems,
            "based_on": SolverKind.CP_SAT.value if use_cp else SolverKind.GREEDY.value,
        }
        e_m["selected"] = not e_problems

        ctx.check_cancelled()
        s.execute(delete(ScheduleRun).where(ScheduleRun.project_id == pid))
        runs = [
            (SolverKind.GREEDY, DescriptionMode.STANDARD, g_m, greedy_ms, g_ok, greedy_placed),
            (SolverKind.CP_SAT, DescriptionMode.STANDARD, c_m, cp_ms, cp_ok, cp.placed),
        ]
        for solver, mode, m, ms, ok, placed in runs:
            run = ScheduleRun(
                project_id=pid,
                solver=solver,
                mode=mode,
                status=ScheduleStatus.SUCCEEDED if ok else ScheduleStatus.FAILED,
                params=params,
                metrics=m,
                duration_ms=round(ms, 3),
            )
            s.add(run)
            s.flush()
            if ok:
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
        ext_run = ScheduleRun(
            project_id=pid,
            solver=SolverKind.CP_SAT if use_cp else SolverKind.GREEDY,
            mode=DescriptionMode.EXTENDED,
            status=ScheduleStatus.FAILED if e_problems else ScheduleStatus.SUCCEEDED,
            params=params | {"pause_budget_pct": cfg.extended_pause_budget_pct},
            metrics=e_m,
        )
        s.add(ext_run)
        s.flush()
        if not e_problems:
            s.add_all(
                SchedulePlacement(
                    run_id=ext_run.id,
                    cue_id=p.cue_id,
                    variant=p.variant,
                    start_s=p.start_s,
                    end_s=p.end_s,
                    inserted_pause_s=p.pause_s,
                    pause_reason=p.reason,
                )
                for p in ext.placements
            )
        if (g_ok or cp_ok) and not e_problems:
            queue_synthesis(s, pid)
        s.commit()
    if not (g_ok or cp_ok) or e_problems:
        log.error("project %s: invalid schedule: %s %s", pid, g_m["violations"], e_problems)
        raise PermanentJobError("A schedule failed its overlap check and was not used.")
    log.info(
        "project %s: greedy %d / cp-sat %d (%s) placed, extended %d paused (%.1f s), %d held",
        pid,
        len(greedy_placed),
        len(cp.placed),
        cp.status,
        len(ext.pauses),
        ext.paused_s,
        len(held),
    )
    ctx.progress("schedule", 1.0)
