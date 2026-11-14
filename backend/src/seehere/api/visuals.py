"""Visual units and their seen-versus-said scores (Tasks 12-13)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from seehere.api.errors import APIError
from seehere.db.enums import JobStatus, VisualKind
from seehere.db.models import Job, Project, VisualUnit
from seehere.db.session import get_db
from seehere.vision import coverage, units

router = APIRouter(prefix="/api", tags=["visuals"])

DbDep = Annotated[Session, Depends(get_db)]


class UnitOut(BaseModel):
    id: uuid.UUID
    frame_id: uuid.UUID
    kind: VisualKind
    label: str
    lines: list[str]
    details: str
    # box as fractions of the frame (0..1)
    x: float | None
    y: float | None
    w: float | None
    h: float | None
    t_start_s: float
    t_end_s: float
    source: str  # "ocr" or the vision model that produced it
    coverage: float | None  # 0 = never said aloud, 1 = fully said; None until scored
    priority: float | None
    said: list[str]
    unsaid: list[str]


class VisualsOut(BaseModel):
    available: bool  # False until visual analysis has finished
    scored: bool  # True once units were compared with the transcript
    units: list[UnitOut] = []


def _succeeded(db: Session, project_id: uuid.UUID, kind: str) -> bool:
    return (
        db.scalar(
            select(Job.id).where(
                Job.project_id == project_id, Job.kind == kind, Job.status == JobStatus.SUCCEEDED
            )
        )
        is not None
    )


@router.get("/projects/{project_id}/visuals", response_model=VisualsOut)
def get_visuals(project_id: uuid.UUID, db: DbDep) -> VisualsOut:
    """Units ordered by priority (most needing description first), then by time."""
    if db.get(Project, project_id) is None:
        raise APIError(404, "not_found", "No project with this ID.")
    if not _succeeded(db, project_id, units.JOB_KIND):
        return VisualsOut(available=False, scored=False)
    rows = list(db.scalars(select(VisualUnit).where(VisualUnit.project_id == project_id)))
    rows.sort(key=lambda u: (-(u.priority or 0.0), u.t_start_s, u.y or 0.0))
    return VisualsOut(
        available=True,
        scored=_succeeded(db, project_id, coverage.JOB_KIND)
        and any(u.coverage_score is not None for u in rows),
        units=[
            UnitOut(
                id=u.id,
                frame_id=u.frame_id,
                kind=u.kind,
                label=u.label,
                lines=u.values.get("lines", []),
                details=u.values.get("details", ""),
                x=u.x,
                y=u.y,
                w=u.w,
                h=u.h,
                t_start_s=u.t_start_s,
                t_end_s=u.t_end_s,
                source=u.source,
                coverage=u.coverage_score,
                priority=u.priority,
                said=u.values.get("said", []),
                unsaid=u.values.get("unsaid", []),
            )
            for u in rows
        ],
    )
