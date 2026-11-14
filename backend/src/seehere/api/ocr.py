"""On-screen text read from each keyframe (Task 10)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from seehere.api.errors import APIError
from seehere.db.enums import JobStatus, MediaKind
from seehere.db.models import Frame, Job, MediaAsset, OcrRegion, Project
from seehere.db.session import get_db
from seehere.media.ocr import JOB_KIND

router = APIRouter(prefix="/api", tags=["ocr"])

DbDep = Annotated[Session, Depends(get_db)]


class RegionOut(BaseModel):
    text: str
    confidence: float
    # box as fractions of the frame (0..1)
    x: float
    y: float
    w: float
    h: float


class KeyframeText(BaseModel):
    frame_id: uuid.UUID
    t_s: float
    regions: list[RegionOut]


class OcrOut(BaseModel):
    available: bool  # False until text recognition has finished for the current keyframes
    keyframes: list[KeyframeText] = []


@router.get("/projects/{project_id}/ocr", response_model=OcrOut)
def get_ocr(project_id: uuid.UUID, db: DbDep) -> OcrOut:
    if db.get(Project, project_id) is None:
        raise APIError(404, "not_found", "No project with this ID.")
    done = db.scalar(
        select(Job.id).where(
            Job.project_id == project_id, Job.kind == JOB_KIND, Job.status == JobStatus.SUCCEEDED
        )
    )
    if done is None:
        return OcrOut(available=False)
    frames = list(
        db.execute(
            select(Frame.id, Frame.t_s)
            .join(MediaAsset, Frame.media_asset_id == MediaAsset.id)
            .where(
                MediaAsset.project_id == project_id,
                MediaAsset.kind == MediaKind.SOURCE_VIDEO,
                Frame.is_keyframe.is_(True),
            )
            .order_by(Frame.t_s)
        )
    )
    regions: dict[uuid.UUID, list[RegionOut]] = {f.id: [] for f in frames}
    for r in db.scalars(
        select(OcrRegion)
        .where(OcrRegion.frame_id.in_(list(regions)))
        .order_by(OcrRegion.y, OcrRegion.x)
    ):
        regions[r.frame_id].append(
            RegionOut(text=r.text, confidence=r.confidence, x=r.x, y=r.y, w=r.w, h=r.h)
        )
    return OcrOut(
        available=True,
        keyframes=[KeyframeText(frame_id=f.id, t_s=f.t_s, regions=regions[f.id]) for f in frames],
    )
