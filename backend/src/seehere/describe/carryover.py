"""Keep instructor reviews when descriptions are rebuilt (Task 26).

Re-running the analysis (for example after a slide deck is added) rebuilds every description.
Before that, `remember_reviews` records each reviewed description's status, any edited text and
its decision history, keyed by the visual it describes (label and first appearance);
`restore_reviews` re-applies them to the rebuilt description of the same visual.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from seehere.db.enums import ReviewAction, ReviewStatus
from seehere.db.models import DescriptionCue, ReviewDecision, VisualUnit


@dataclass(frozen=True)
class _Kept:
    status: ReviewStatus
    edited: tuple[str, str | None, str | None] | None
    decisions: list[tuple[ReviewAction, str | None, str | None, str | None]]


def _key(unit: VisualUnit | None) -> tuple[str, float] | None:
    return (unit.label, round(unit.t_start_s, 1)) if unit else None


def remember_reviews(s: Session, project_id: uuid.UUID) -> dict[tuple[str, float], _Kept]:
    """Before descriptions are rebuilt: the review state of every reviewed description, keyed
    by the visual it describes (label and first appearance)."""
    kept = {}
    rows = s.execute(
        select(DescriptionCue, VisualUnit)
        .join(VisualUnit, DescriptionCue.visual_unit_id == VisualUnit.id)
        .where(DescriptionCue.project_id == project_id)
    )
    for cue, unit in rows:
        decisions = list(
            s.scalars(
                select(ReviewDecision)
                .where(ReviewDecision.cue_id == cue.id)
                .order_by(ReviewDecision.created_at)
            )
        )
        key = _key(unit)
        if not decisions or key is None:
            continue
        last_text = next(
            (
                d.action
                for d in reversed(decisions)
                if d.action in (ReviewAction.EDIT, ReviewAction.REGENERATE)
            ),
            None,
        )
        kept[key] = _Kept(
            cue.review_status,
            (cue.text_short, cue.text_medium, cue.text_long)
            if last_text is ReviewAction.EDIT
            else None,
            [(d.action, d.previous_text, d.new_text, d.note) for d in decisions],
        )
    return kept


def restore_reviews(
    s: Session,
    cues: list[DescriptionCue],
    units: dict[uuid.UUID, VisualUnit],
    kept: dict[tuple[str, float], _Kept],
) -> int:
    """After rebuilding: re-apply remembered review state to the matching new descriptions.
    Returns how many were restored. Does not commit."""
    restored = 0
    for cue in cues:
        key = _key(units.get(cue.visual_unit_id)) if cue.visual_unit_id else None
        k = kept.get(key) if key else None
        if k is None:
            continue
        cue.review_status = k.status
        if k.edited:
            cue.text_short, cue.text_medium, cue.text_long = k.edited
        s.flush()
        s.add_all(
            ReviewDecision(cue_id=cue.id, action=a, previous_text=p, new_text=n, note=nt)
            for a, p, n, nt in k.decisions
        )
        restored += 1
    return restored
