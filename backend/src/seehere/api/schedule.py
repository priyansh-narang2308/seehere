"""The latest standard-mode schedule: speech windows, placed cues and why others were not."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from seehere.api.errors import APIError
from seehere.db.enums import (
    DescriptionMode,
    DescriptionVariant,
    ScheduleStatus,
    SolverKind,
    VerificationState,
)
from seehere.db.models import DescriptionCue, Project, SchedulePlacement, ScheduleRun
from seehere.db.session import get_db

router = APIRouter(prefix="/api", tags=["schedule"])

DbDep = Annotated[Session, Depends(get_db)]


class WindowOut(BaseModel):
    start_s: float
    end_s: float


class PlacementOut(BaseModel):
    cue_id: uuid.UUID
    variant: DescriptionVariant
    text: str
    start_s: float
    end_s: float
    verification_state: VerificationState


class NotPlacedOut(BaseModel):
    cue_id: uuid.UUID
    text: str
    reason: str


class ScheduleOut(BaseModel):
    available: bool
    solver: SolverKind | None = None
    mode: DescriptionMode | None = None
    status: ScheduleStatus | None = None
    windows: list[WindowOut] = []
    placements: list[PlacementOut] = []
    not_placed: list[NotPlacedOut] = []
    priority_placed_share: float | None = None
    duration_ms: float | None = None


_HELD = "needs review: held back until an instructor approves it"


@router.get("/projects/{project_id}/schedule", response_model=ScheduleOut)
def get_schedule(project_id: uuid.UUID, db: DbDep) -> ScheduleOut:
    if db.get(Project, project_id) is None:
        raise APIError(404, "not_found", "No project with this ID.")
    run = db.scalars(
        select(ScheduleRun)
        .where(ScheduleRun.project_id == project_id)
        .order_by(ScheduleRun.created_at.desc())
    ).first()
    if run is None:
        return ScheduleOut(available=False)
    cues = {
        c.id: c
        for c in db.scalars(select(DescriptionCue).where(DescriptionCue.project_id == project_id))
    }
    texts = {
        DescriptionVariant.SHORT: lambda c: c.text_short,
        DescriptionVariant.MEDIUM: lambda c: c.text_medium,
        DescriptionVariant.LONG: lambda c: c.text_long,
    }
    placements = []
    for p in db.scalars(
        select(SchedulePlacement)
        .where(SchedulePlacement.run_id == run.id)
        .order_by(SchedulePlacement.start_s)
    ):
        cue = cues[p.cue_id]
        placements.append(
            PlacementOut(
                cue_id=p.cue_id,
                variant=p.variant,
                text=texts[p.variant](cue) or cue.text_short,
                start_s=p.start_s,
                end_s=p.end_s,
                verification_state=cue.verification_state,
            )
        )
    m = run.metrics
    not_placed = [
        NotPlacedOut(cue_id=cid, text=cues[cid].text_short, reason=reason)
        for cid, reason in [
            *((uuid.UUID(k["cue_id"]), k["reason"]) for k in m.get("skipped", [])),
            *((uuid.UUID(k), _HELD) for k in m.get("held_for_review", [])),
        ]
        if cid in cues
    ]
    return ScheduleOut(
        available=True,
        solver=run.solver,
        mode=run.mode,
        status=run.status,
        windows=[WindowOut(start_s=a, end_s=b) for a, b in m.get("windows", [])],
        placements=placements,
        not_placed=sorted(not_placed, key=lambda n: cues[n.cue_id].anchor_t_s),
        priority_placed_share=m.get("priority_placed_share"),
        duration_ms=run.duration_ms,
    )
