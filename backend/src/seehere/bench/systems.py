"""System outputs for the benchmark, each with its evidence label.

- SeeHere greedy / CP-SAT (standard) and extended: the stored schedule runs of a processed
  project, OBSERVED;
- SeeHere reviewed: OBSERVED when an instructor recorded review decisions on the project;
  otherwise SIMULATED by re-planning in a rolled-back transaction as if a reviewer approved
  every held description unchanged (wordings without audio use the duration estimate);
- Microsoft ai-audio-descriptions: the WebVTT its GenerateAD CLI wrote for this video,
  OBSERVED; UNAVAILABLE when no such file was produced (it needs an Azure Foundry resource).
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from seehere.bench.metrics import Said
from seehere.core.config import Settings
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
    ReviewDecision,
    SchedulePlacement,
    ScheduleRun,
)

OBSERVED, SIMULATED, UNAVAILABLE = "OBSERVED", "SIMULATED", "UNAVAILABLE"


@dataclass
class SystemRun:
    system: str
    label: str  # OBSERVED, SIMULATED or UNAVAILABLE
    said: list[Said] = field(default_factory=list)
    note: str = ""


class BenchError(RuntimeError):
    pass


def source_sha256(s: Session, pid: uuid.UUID) -> str | None:
    return s.scalar(
        select(MediaAsset.sha256).where(
            MediaAsset.project_id == pid, MediaAsset.kind == MediaKind.SOURCE_VIDEO
        )
    )


def _text(cue: DescriptionCue, variant: DescriptionVariant) -> str:
    return {
        DescriptionVariant.SHORT: cue.text_short,
        DescriptionVariant.MEDIUM: cue.text_medium,
        DescriptionVariant.LONG: cue.text_long,
    }[variant] or cue.text_short


def _said(s: Session, run: ScheduleRun) -> list[Said]:
    cues = {
        c.id: c
        for c in s.scalars(
            select(DescriptionCue).where(DescriptionCue.project_id == run.project_id)
        )
    }
    return [
        Said(p.start_s, p.end_s, _text(cues[p.cue_id], p.variant), p.inserted_pause_s)
        for p in s.scalars(
            select(SchedulePlacement)
            .where(SchedulePlacement.run_id == run.id)
            .order_by(SchedulePlacement.start_s)
        )
    ]


def _runs(s: Session, pid: uuid.UUID) -> list[ScheduleRun]:
    return list(
        s.scalars(
            select(ScheduleRun).where(
                ScheduleRun.project_id == pid, ScheduleRun.status == ScheduleStatus.SUCCEEDED
            )
        )
    )


def _pick(runs: list[ScheduleRun], mode: DescriptionMode, solver: SolverKind | None) -> ScheduleRun:
    for r in runs:
        if r.mode is not mode:
            continue
        if (solver is None and r.metrics.get("selected")) or r.solver is solver:
            return r
    raise BenchError(f"the project has no successful {mode.value} {solver or ''} schedule")


def seehere_systems(s: Session, cfg: Settings, pid: uuid.UUID) -> list[SystemRun]:
    runs = _runs(s, pid)
    greedy = _pick(runs, DescriptionMode.STANDARD, SolverKind.GREEDY)
    cp = _pick(runs, DescriptionMode.STANDARD, SolverKind.CP_SAT)
    ext = _pick(runs, DescriptionMode.EXTENDED, None)
    selected = _pick(runs, DescriptionMode.STANDARD, None)
    out = [
        SystemRun("seehere-greedy", OBSERVED, _said(s, greedy), "stored greedy schedule"),
        SystemRun(
            "seehere-cp-sat", OBSERVED, _said(s, cp), f"status {cp.metrics.get('solver_status')}"
        ),
        SystemRun("seehere-extended", OBSERVED, _said(s, ext), f"built on {ext.solver.value}"),
    ]
    decisions = s.scalar(
        select(func.count(ReviewDecision.id))
        .join(DescriptionCue, ReviewDecision.cue_id == DescriptionCue.id)
        .where(DescriptionCue.project_id == pid)
    )
    if decisions:
        out.append(
            SystemRun(
                "seehere-reviewed",
                OBSERVED,
                _said(s, selected),
                f"{decisions} instructor decisions recorded; "
                f"selected {selected.solver.value} schedule",
            )
        )
    else:
        out.append(_simulated_review(s, cfg, pid))
    return out


def _simulated_review(s: Session, cfg: Settings, pid: uuid.UUID) -> SystemRun:
    from seehere.schedule.plan import build_schedules  # import cycle via speech synthesis

    held = list(
        s.scalars(
            select(DescriptionCue).where(
                DescriptionCue.project_id == pid,
                DescriptionCue.verification_state == VerificationState.NEEDS_REVIEW,
                DescriptionCue.review_status == ReviewStatus.PENDING,
            )
        )
    )
    s.commit()  # start the throwaway transaction from a clean state
    try:
        for c in held:
            c.review_status = ReviewStatus.APPROVED
        s.flush()
        build_schedules(s, cfg, pid, progress=lambda *_: None, check=lambda: None)
        said = _said(s, _pick(_runs(s, pid), DescriptionMode.STANDARD, None))
    finally:
        s.rollback()  # nothing is kept
    note = (
        f"assumes a reviewer approves all {len(held)} held descriptions unchanged"
        if held
        else "no description was held for review, so an approving reviewer changes nothing"
    )
    return SystemRun("seehere-reviewed", SIMULATED, said, note)


_TIME = r"(?:(\d+):)?(\d{1,2}):(\d{2}(?:\.\d{1,3})?)"
_CUE = re.compile(rf"^{_TIME}\s+-->\s+{_TIME}")


def _secs(h: str | None, m: str, sec: str) -> float:
    return int(h or 0) * 3600 + int(m) * 60 + float(sec)


def parse_webvtt(text: str) -> list[Said]:
    """Cues of a WebVTT file as (start, end, text). Tags such as <v> are removed."""
    out = []
    lines = text.replace("\r\n", "\n").split("\n")
    i = 0
    while i < len(lines):
        m = _CUE.match(lines[i].strip())
        i += 1
        if not m:
            continue
        body = []
        while i < len(lines) and lines[i].strip():
            body.append(re.sub(r"<[^>]+>", "", lines[i]).strip())
            i += 1
        start, end = _secs(*m.groups()[:3]), _secs(*m.groups()[3:])
        if end > start and body:
            out.append(Said(start, end, " ".join(body)))
    return out


def microsoft_system(vtt: Path | None) -> SystemRun:
    name = "microsoft-ai-audio-descriptions"
    if vtt is None or not vtt.is_file():
        return SystemRun(
            name,
            UNAVAILABLE,
            note="not run: GenerateAD needs an Azure Foundry resource (Speech + GPT), which is "
            "chargeable and was not provisioned. See bench/microsoft/README.md.",
        )
    said = parse_webvtt(vtt.read_text("utf-8"))
    return SystemRun(name, OBSERVED, said, f"GenerateAD output {vtt.name}")
