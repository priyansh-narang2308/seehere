"""The timed transcript produced by speech-to-text (Task 08)."""

from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from seehere.api.errors import APIError
from seehere.db.enums import MediaKind
from seehere.db.models import MediaAsset, Project, TranscriptSegment, TranscriptWord
from seehere.db.session import get_db

router = APIRouter(prefix="/api", tags=["transcript"])

DbDep = Annotated[Session, Depends(get_db)]


class WordOut(BaseModel):
    text: str
    start_s: float
    end_s: float
    confidence: float | None


class SegmentOut(BaseModel):
    start_s: float
    end_s: float
    text: str
    words: list[WordOut]


class TranscriptOut(BaseModel):
    # False until speech-to-text has finished for the current audio.
    available: bool
    provider: str | None = None
    language: str | None = None
    duration_s: float | None = None
    word_count: int = 0
    segments: list[SegmentOut] = []


@router.get("/projects/{project_id}/transcript", response_model=TranscriptOut)
def get_transcript(project_id: uuid.UUID, db: DbDep) -> TranscriptOut:
    if db.get(Project, project_id) is None:
        raise APIError(404, "not_found", "No project with this ID.")
    audio = db.scalars(
        select(MediaAsset).where(
            MediaAsset.project_id == project_id, MediaAsset.kind == MediaKind.NORMALIZED_AUDIO
        )
    ).first()
    meta = ((audio.probe or {}).get("transcript") if audio else None) or None
    if audio is None or meta is None:
        return TranscriptOut(available=False)

    words: dict[uuid.UUID, list[WordOut]] = defaultdict(list)
    for w in db.scalars(
        select(TranscriptWord)
        .where(TranscriptWord.media_asset_id == audio.id)
        .order_by(TranscriptWord.idx)
    ):
        words[w.segment_id].append(
            WordOut(text=w.text, start_s=w.start_s, end_s=w.end_s, confidence=w.confidence)
        )
    segments = [
        SegmentOut(start_s=s.start_s, end_s=s.end_s, text=s.text, words=words[s.id])
        for s in db.scalars(
            select(TranscriptSegment)
            .where(TranscriptSegment.media_asset_id == audio.id)
            .order_by(TranscriptSegment.idx)
        )
    ]
    return TranscriptOut(
        available=True,
        provider=meta.get("provider"),
        language=meta.get("language"),
        duration_s=audio.duration_s,
        word_count=sum(len(s.words) for s in segments),
        segments=segments,
    )
