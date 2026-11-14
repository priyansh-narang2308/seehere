"""Coverage and verification report (Task 28): what happened to every visual on screen.

Each visual unit gets exactly one outcome:
- `said_aloud`: the speaker said everything it shows, so nothing is described;
- `repeat`: the same text on the same frame was already described;
- `described`: voiced in the standard schedule (no pause);
- `described_extended`: voiced only in extended mode, where the video pauses;
- `skipped`: a description exists but found no room (the scheduler's reason is kept);
- `held_for_review`: its claims are unsupported and no instructor has approved it;
- `rejected`: an instructor rejected the description;
- `not_scheduled`: descriptions exist but no schedule has been computed yet.
Units whose outcome is skipped, held, rejected or not scheduled are *uncovered*: on screen,
not fully said aloud, and not described to the listener.

Counts of verification states describe evidence checks (OCR and deck text), not complete fact
checking, and the report is not a WCAG conformance certification.
"""

from __future__ import annotations

import html
import uuid
from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from seehere.db.enums import (
    DescriptionMode,
    JobStatus,
    ReviewStatus,
    ScheduleStatus,
    VerificationState,
)
from seehere.db.models import (
    DescriptionCue,
    Job,
    SchedulePlacement,
    ScheduleRun,
    VerificationEvent,
    VisualUnit,
)

NOTICE = (
    "Verification states record whether quotes and numbers match text read on screen or in the "
    "slide deck. That is evidence, not complete fact-checking. This report is not a WCAG "
    "conformance certification."
)
OUTCOMES = (
    "described",
    "described_extended",
    "said_aloud",
    "repeat",
    "skipped",
    "held_for_review",
    "rejected",
    "not_scheduled",
)
UNCOVERED = {"skipped", "held_for_review", "rejected", "not_scheduled"}
OUTCOME_LABEL = {
    "described": "Described",
    "described_extended": "Described in extended mode (video pauses)",
    "said_aloud": "Said aloud by the speaker",
    "repeat": "Already described on this frame",
    "skipped": "Not described: no room",
    "held_for_review": "Not described: waiting for review",
    "rejected": "Not described: rejected by the instructor",
    "not_scheduled": "Not described: not scheduled yet",
}
STATE_LABEL = {
    VerificationState.VERIFIED_TEXT_MATCH: "Verified text match",
    VerificationState.CORROBORATED: "Corroborated",
    VerificationState.UNCERTAIN: "Uncertain",
    VerificationState.NEEDS_REVIEW: "Needs human review",
}


@dataclass(frozen=True)
class UnitFact:
    id: uuid.UUID
    kind: str
    label: str
    t_start_s: float
    t_end_s: float
    coverage: float | None


@dataclass(frozen=True)
class CueFact:
    id: uuid.UUID
    unit_id: uuid.UUID | None
    text: str
    state: VerificationState
    review: ReviewStatus


@dataclass
class ScheduleFacts:
    scheduled: bool = False
    standard: set[uuid.UUID] = field(default_factory=set)
    extended: dict[uuid.UUID, tuple[float, str | None]] = field(default_factory=dict)
    skipped: dict[uuid.UUID, str] = field(default_factory=dict)  # standard-mode reasons
    skipped_extended: dict[uuid.UUID, str] = field(default_factory=dict)
    held: set[uuid.UUID] = field(default_factory=set)
    timing: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Item:
    visual_unit_id: str
    kind: str
    label: str
    t_start_s: float
    t_end_s: float
    coverage: float | None
    outcome: str
    reason: str | None
    cue_id: str | None
    text: str | None
    verification_state: str | None
    review_status: str | None
    pause_s: float | None


def _outcome(
    unit: UnitFact, cue: CueFact | None, sched: ScheduleFacts
) -> tuple[str, str | None, float | None]:
    if cue is None:
        if (unit.coverage or 0.0) >= 1.0:
            return "said_aloud", "every line on it was said aloud", None
        return "repeat", "the same text on this frame is already described", None
    if cue.review is ReviewStatus.REJECTED:
        return "rejected", "an instructor rejected the description", None
    if not sched.scheduled:
        return "not_scheduled", "the schedule has not been computed yet", None
    if cue.id in sched.held:
        return "held_for_review", "a claim is not supported by the evidence", None
    if cue.id in sched.standard:
        return "described", None, None
    if cue.id in sched.extended:
        pause, reason = sched.extended[cue.id]
        return "described_extended", reason, pause
    reason = sched.skipped_extended.get(cue.id) or sched.skipped.get(cue.id)
    return "skipped", reason or "no room in either mode", None


def build_report(
    units: list[UnitFact],
    cues: list[CueFact],
    sched: ScheduleFacts,
    checks: Counter[str],
) -> dict[str, Any]:
    """The report as plain JSON-ready data. Pure: same facts, same report."""
    by_unit = {c.unit_id: c for c in cues if c.unit_id is not None}
    items = []
    for u in sorted(units, key=lambda u: (u.t_start_s, u.label, str(u.id))):
        cue = by_unit.get(u.id)
        outcome, reason, pause = _outcome(u, cue, sched)
        items.append(
            Item(
                visual_unit_id=str(u.id),
                kind=u.kind,
                label=u.label,
                t_start_s=u.t_start_s,
                t_end_s=u.t_end_s,
                coverage=u.coverage,
                outcome=outcome,
                reason=reason,
                cue_id=str(cue.id) if cue else None,
                text=cue.text if cue else None,
                verification_state=cue.state.value if cue else None,
                review_status=cue.review.value if cue else None,
                pause_s=pause,
            )
        )
    outcomes = Counter(i.outcome for i in items)
    states = Counter(c.state.value for c in cues)
    reviews = Counter(c.review.value for c in cues)
    return {
        "available": True,
        "summary": {
            "visual_units": len(items),
            **{k: outcomes.get(k, 0) for k in OUTCOMES},
            "uncovered": sum(outcomes.get(k, 0) for k in UNCOVERED),
            "descriptions": len(cues),
        },
        "verification": {s.value: states.get(s.value, 0) for s in VerificationState},
        "checks": {k: checks.get(k, 0) for k in ("pass", "fail", "inconclusive")},
        "review": {r.value: reviews.get(r.value, 0) for r in ReviewStatus},
        "timing": sched.timing,
        "items": [asdict(i) for i in items],
        "notice": NOTICE,
    }


def load_report(s: Session, pid: uuid.UUID) -> dict[str, Any]:
    """Gather the facts for one project and build its report."""
    written = s.scalar(
        select(Job.id).where(
            Job.project_id == pid,
            Job.kind == "descriptions.generate",
            Job.status == JobStatus.SUCCEEDED,
        )
    )
    if written is None:
        return {"available": False}
    units = [
        UnitFact(u.id, u.kind.value, u.label, u.t_start_s, u.t_end_s, u.coverage_score)
        for u in s.scalars(select(VisualUnit).where(VisualUnit.project_id == pid))
    ]
    cues = [
        CueFact(c.id, c.visual_unit_id, c.text_short, c.verification_state, c.review_status)
        for c in s.scalars(select(DescriptionCue).where(DescriptionCue.project_id == pid))
    ]
    checks: Counter[str] = Counter(
        r.value
        for r in s.scalars(
            select(VerificationEvent.result).where(
                VerificationEvent.cue_id.in_([c.id for c in cues])
            )
        )
    )
    return build_report(units, cues, _schedule_facts(s, pid), checks)


def _schedule_facts(s: Session, pid: uuid.UUID) -> ScheduleFacts:
    runs = list(
        s.scalars(
            select(ScheduleRun).where(
                ScheduleRun.project_id == pid, ScheduleRun.status == ScheduleStatus.SUCCEEDED
            )
        )
    )
    std = next(
        (r for r in runs if r.mode is DescriptionMode.STANDARD and r.metrics.get("selected")),
        None,
    )
    ext = next(
        (r for r in runs if r.mode is DescriptionMode.EXTENDED and r.metrics.get("selected")),
        None,
    )
    facts = ScheduleFacts()
    if std is None:
        return facts
    facts.scheduled = True
    facts.standard = set(
        s.scalars(select(SchedulePlacement.cue_id).where(SchedulePlacement.run_id == std.id))
    )
    facts.skipped = {uuid.UUID(k["cue_id"]): k["reason"] for k in std.metrics.get("skipped", [])}
    facts.held = {uuid.UUID(c) for c in std.metrics.get("held_for_review", [])}
    facts.timing["standard"] = {
        "solver": std.solver.value,
        "round": std.round,
        "check": std.metrics.get("timing"),
        "priority_placed_share": std.metrics.get("priority_placed_share"),
        "described_s": std.metrics.get("described_s"),
        "comparison": std.metrics.get("comparison"),
    }
    if ext is not None:
        for p in s.scalars(select(SchedulePlacement).where(SchedulePlacement.run_id == ext.id)):
            if p.cue_id not in facts.standard:
                facts.extended[p.cue_id] = (p.inserted_pause_s, p.pause_reason)
        facts.skipped_extended = {
            uuid.UUID(k["cue_id"]): k["reason"] for k in ext.metrics.get("skipped", [])
        }
        facts.timing["extended"] = {
            "solver": ext.solver.value,
            "round": ext.round,
            "check": ext.metrics.get("timing"),
            "budget_s": ext.metrics.get("budget_s"),
            "paused_s": ext.metrics.get("paused_s"),
            "extended_duration_s": ext.metrics.get("extended_duration_s"),
        }
    return facts


def report_html(title: str, report: dict[str, Any]) -> str:
    """The report as one accessible HTML page (plain semantic markup, no scripts)."""
    e = html.escape

    def clock(t: float) -> str:
        return f"{int(t // 60)}:{int(t % 60):02d}"

    summary = report["summary"]
    counts = "\n".join(
        f'<tr><th scope="row">{e(OUTCOME_LABEL[k])}</th><td>{summary[k]}</td></tr>'
        for k in OUTCOMES
        if summary[k]
    )
    states = "\n".join(
        f'<tr><th scope="row">{e(STATE_LABEL[VerificationState(k)])}</th><td>{n}</td></tr>'
        for k, n in report["verification"].items()
    )
    rows = []
    for i in report["items"]:
        state = STATE_LABEL[VerificationState(i["verification_state"])] if i["text"] else ""
        cov = "" if i["coverage"] is None else f"{round(i['coverage'] * 100)}%"
        rows.append(
            "<tr>"
            f'<td><time datetime="PT{i["t_start_s"]:.3f}S">{clock(i["t_start_s"])}</time>'
            f"–{clock(i['t_end_s'])}</td>"
            f"<td>{e(i['label'])}</td><td>{cov}</td>"
            f"<td>{e(OUTCOME_LABEL[i['outcome']])}"
            f"{'<br><small>' + e(i['reason']) + '</small>' if i['reason'] else ''}</td>"
            f"<td>{e(i['text'] or '')}</td><td>{e(state)}</td>"
            "</tr>"
        )
    std = report["timing"].get("standard") or {}
    ext = report["timing"].get("extended") or {}
    timing = []
    if std:
        fit = (std.get("check") or {}).get("status", "not checked")
        timing.append(
            f"<li>Standard: {e(str(std['solver']))} schedule, round {std['round']}, "
            f"audio timing {e(str(fit))}.</li>"
        )
    if ext:
        timing.append(
            f"<li>Extended: {ext.get('paused_s') or 0:.1f} s of pauses within a "
            f"{ext.get('budget_s') or 0:.1f} s budget.</li>"
        )
    timing_html = f"<ul>{''.join(timing)}</ul>" if timing else "<p>No schedule yet.</p>"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}: coverage and verification report</title>
<style>
body {{ font: 16px/1.5 system-ui, sans-serif; max-width: 72rem; margin: 2rem auto;
  padding: 0 1rem; color: #1a1a1a; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #bbb; padding: .4rem .6rem; text-align: left; vertical-align: top; }}
small {{ color: #444; }}
</style>
</head>
<body>
<h1>{e(title)}: coverage and verification report</h1>
<p>{e(report["notice"])}</p>
<h2>Summary</h2>
<p>{summary["visual_units"]} visual items found on screen; {summary["uncovered"]} not described
to the listener (uncovered).</p>
<table><caption>Outcomes</caption><tbody>
{counts}
</tbody></table>
<h2>Verification</h2>
<table><caption>Descriptions by verification state</caption><tbody>
{states}
</tbody></table>
<h2>Timing</h2>
{timing_html}
<h2>Every visual item</h2>
<table>
<thead><tr><th scope="col">On screen</th><th scope="col">Visual</th><th scope="col">Said aloud</th>
<th scope="col">Outcome</th><th scope="col">Description</th><th scope="col">Verification</th>
</tr></thead>
<tbody>
{chr(10).join(rows)}
</tbody>
</table>
</body>
</html>
"""
