"""Instructor review (Task 26): approve, reject, edit or regenerate a description.

Every action is recorded as a `review_decision`. An edit replaces the wording with the
instructor's text (one wording, so exactly that text is voiced) and is verified again like any
generated text: an instructor's words are checked, not trusted. Regenerate restores the wording
built from the evidence. Each action re-runs scheduling, which flows on to synthesis, the timing
check and export.

Scheduling uses review status as follows: a rejected cue is never voiced; a cue whose
verification is "needs review" is held back until an instructor approves (or edits) it.

When the analysis is re-run, `describe.carryover` keeps these decisions (see there).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from seehere.db.enums import ReviewAction, ReviewStatus
from seehere.db.models import DescriptionCue, ReviewDecision, VisualUnit
from seehere.describe.generate import write_wordings
from seehere.describe.verify import verify_cue
from seehere.schedule.plan import queue_schedule

MAX_TEXT = 500


class ReviewError(ValueError):
    """The action cannot be applied; the message is safe to show."""


def apply_review(
    s: Session,
    cue: DescriptionCue,
    action: ReviewAction,
    *,
    text: str | None = None,
    note: str | None = None,
) -> ReviewDecision:
    """Apply one instructor action and queue re-scheduling. Does not commit."""
    previous = cue.text_short
    new_text = None
    if action is ReviewAction.APPROVE:
        cue.review_status = ReviewStatus.APPROVED
    elif action is ReviewAction.REJECT:
        cue.review_status = ReviewStatus.REJECTED
    elif action is ReviewAction.EDIT:
        new_text = " ".join((text or "").split())
        if not new_text:
            raise ReviewError("Write the new description before saving.")
        if len(new_text) > MAX_TEXT:
            raise ReviewError(f"Keep the description under {MAX_TEXT} characters.")
        cue.text_short, cue.text_medium, cue.text_long = new_text, None, None
        cue.review_status = ReviewStatus.APPROVED
        verify_cue(s, cue)
    elif action is ReviewAction.REGENERATE:
        unit = s.get(VisualUnit, cue.visual_unit_id) if cue.visual_unit_id else None
        if unit is None:
            raise ReviewError("This description has no visual to rebuild it from.")
        w = write_wordings(
            unit.kind, unit.label, unit.values.get("lines", []), unit.values.get("details", "")
        )
        cue.text_short, cue.text_medium, cue.text_long = w.short, w.medium, w.long
        new_text = w.short
        cue.review_status = ReviewStatus.PENDING
        verify_cue(s, cue)
    decision = ReviewDecision(
        cue_id=cue.id,
        action=action,
        previous_text=previous,
        new_text=new_text,
        note=(note or "").strip()[:1000] or None,
    )
    s.add(decision)
    queue_schedule(s, cue.project_id)
    return decision
