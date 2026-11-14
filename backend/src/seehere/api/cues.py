"""Description cues, their evidence ledger (Task 15), and spoken visual references (Task 14)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from seehere.api.errors import APIError
from seehere.db.enums import (
    CheckResult,
    EvidenceKind,
    JobStatus,
    ReferenceStatus,
    ReviewStatus,
    VerificationState,
    VisualKind,
)
from seehere.db.models import (
    DescriptionCue,
    Evidence,
    Frame,
    Job,
    OcrRegion,
    Project,
    ReferenceLink,
    Slide,
    TranscriptWord,
    VerificationEvent,
    VisualUnit,
)
from seehere.db.session import get_db
from seehere.describe import generate
from seehere.references import resolve
from seehere.text.words import join_words

router = APIRouter(prefix="/api", tags=["cues"])

DbDep = Annotated[Session, Depends(get_db)]


class Box(BaseModel):
    x: float
    y: float
    w: float
    h: float


class CueOut(BaseModel):
    id: uuid.UUID
    visual_unit_id: uuid.UUID | None
    text_short: str
    text_medium: str | None
    text_long: str | None
    anchor_t_s: float
    priority: float
    verification_state: VerificationState
    review_status: ReviewStatus


class CuesOut(BaseModel):
    available: bool  # False until descriptions have been written
    cues: list[CueOut] = []


class FrameOut(BaseModel):
    id: uuid.UUID
    t_s: float
    image_url: str


class OcrOut(BaseModel):
    text: str
    confidence: float
    box: Box


class SlideOut(BaseModel):
    page: int
    text: str
    score: float | None


class UnitOut(BaseModel):
    kind: VisualKind
    label: str
    lines: list[str]
    details: str
    box: Box | None
    t_start_s: float
    t_end_s: float
    source: str
    coverage: float | None
    said: list[str]
    unsaid: list[str]


class SpanOut(BaseModel):
    start_s: float
    end_s: float
    text: str


class EvidenceOut(BaseModel):
    kind: EvidenceKind
    note: str | None
    frame: FrameOut | None = None
    ocr_region: OcrOut | None = None
    slide: SlideOut | None = None
    visual_unit: UnitOut | None = None
    transcript: SpanOut | None = None


class CheckOut(BaseModel):
    claim: str
    check: str
    result: CheckResult
    resulting_state: VerificationState
    detail: dict[str, Any]


class LedgerOut(BaseModel):
    cue: CueOut
    evidence: list[EvidenceOut]
    checks: list[CheckOut]  # claim verification (Task 17); empty until then


class ReferenceOut(BaseModel):
    phrase: str
    t_s: float
    status: ReferenceStatus  # linked, ambiguous (needs review) or unresolved (nothing on screen)
    confidence: float
    visual_unit_id: uuid.UUID | None
    label: str | None


class ReferencesOut(BaseModel):
    available: bool
    references: list[ReferenceOut] = []


def _project(db: Session, project_id: uuid.UUID) -> None:
    if db.get(Project, project_id) is None:
        raise APIError(404, "not_found", "No project with this ID.")


def _done(db: Session, project_id: uuid.UUID, kind: str) -> bool:
    return (
        db.scalar(
            select(Job.id).where(
                Job.project_id == project_id, Job.kind == kind, Job.status == JobStatus.SUCCEEDED
            )
        )
        is not None
    )


def _cue(c: DescriptionCue) -> CueOut:
    return CueOut.model_validate(c, from_attributes=True)


def _box(x: float | None, y: float | None, w: float | None, h: float | None) -> Box | None:
    return None if x is None or y is None or w is None or h is None else Box(x=x, y=y, w=w, h=h)


@router.get("/projects/{project_id}/cues", response_model=CuesOut)
def list_cues(project_id: uuid.UUID, db: DbDep) -> CuesOut:
    _project(db, project_id)
    if not _done(db, project_id, generate.JOB_KIND):
        return CuesOut(available=False)
    cues = db.scalars(
        select(DescriptionCue)
        .where(DescriptionCue.project_id == project_id)
        .order_by(DescriptionCue.anchor_t_s, DescriptionCue.priority.desc())
    )
    return CuesOut(available=True, cues=[_cue(c) for c in cues])


def _span(db: Session, start_id: uuid.UUID, end_id: uuid.UUID) -> SpanOut | None:
    start, end = db.get(TranscriptWord, start_id), db.get(TranscriptWord, end_id)
    if start is None or end is None:
        return None
    words = db.scalars(
        select(TranscriptWord.text)
        .where(
            TranscriptWord.media_asset_id == start.media_asset_id,
            TranscriptWord.idx.between(start.idx, end.idx),
        )
        .order_by(TranscriptWord.idx)
    )
    return SpanOut(start_s=start.start_s, end_s=end.end_s, text=join_words(list(words)))


def _evidence(db: Session, e: Evidence) -> EvidenceOut:
    out = EvidenceOut(kind=e.kind, note=e.note)
    if e.frame_id and (f := db.get(Frame, e.frame_id)):
        out.frame = FrameOut(id=f.id, t_s=f.t_s, image_url=f"/api/frames/{f.id}/image")
    if e.ocr_region_id and (r := db.get(OcrRegion, e.ocr_region_id)):
        out.ocr_region = OcrOut(
            text=r.text, confidence=r.confidence, box=Box(x=r.x, y=r.y, w=r.w, h=r.h)
        )
    if e.slide_id and (sl := db.get(Slide, e.slide_id)):
        out.slide = SlideOut(page=sl.page_number, text=sl.text, score=sl.alignment_score)
    if e.visual_unit_id and (u := db.get(VisualUnit, e.visual_unit_id)):
        out.visual_unit = UnitOut(
            kind=u.kind,
            label=u.label,
            lines=u.values.get("lines", []),
            details=u.values.get("details", ""),
            box=_box(u.x, u.y, u.w, u.h),
            t_start_s=u.t_start_s,
            t_end_s=u.t_end_s,
            source=u.source,
            coverage=u.coverage_score,
            said=u.values.get("said", []),
            unsaid=u.values.get("unsaid", []),
        )
    if e.start_word_id and e.end_word_id:
        out.transcript = _span(db, e.start_word_id, e.end_word_id)
    return out


_ORDER = list(EvidenceKind)


@router.get("/cues/{cue_id}/evidence", response_model=LedgerOut)
def cue_evidence(cue_id: uuid.UUID, db: DbDep) -> LedgerOut:
    """Everything a cue rests on: the visual unit, keyframe, text read, deck page, speech."""
    cue = db.get(DescriptionCue, cue_id)
    if cue is None:
        raise APIError(404, "not_found", "No description with this ID.")
    rows = sorted(cue.evidence, key=lambda e: (_ORDER.index(e.kind), e.note or ""))
    checks = db.scalars(
        select(VerificationEvent)
        .where(VerificationEvent.cue_id == cue_id)
        .order_by(VerificationEvent.created_at)
    )
    return LedgerOut(
        cue=_cue(cue),
        evidence=[_evidence(db, e) for e in rows],
        checks=[
            CheckOut(
                claim=c.claim,
                check=c.check_name,
                result=c.result,
                resulting_state=c.resulting_state,
                detail=c.detail,
            )
            for c in checks
        ],
    )


@router.get("/projects/{project_id}/references", response_model=ReferencesOut)
def list_references(project_id: uuid.UUID, db: DbDep) -> ReferencesOut:
    _project(db, project_id)
    if not _done(db, project_id, resolve.JOB_KIND):
        return ReferencesOut(available=False)
    rows = db.execute(
        select(ReferenceLink, VisualUnit.label)
        .outerjoin(VisualUnit, ReferenceLink.visual_unit_id == VisualUnit.id)
        .where(ReferenceLink.project_id == project_id)
        .order_by(ReferenceLink.t_s)
    )
    return ReferencesOut(
        available=True,
        references=[
            ReferenceOut(
                phrase=r.phrase,
                t_s=r.t_s,
                status=r.status,
                confidence=r.confidence,
                visual_unit_id=r.visual_unit_id,
                label=label,
            )
            for r, label in rows
        ],
    )
