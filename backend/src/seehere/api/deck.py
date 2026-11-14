"""Optional slide deck for a project (Task 11): upload a PDF or PPTX, read its aligned pages."""

from __future__ import annotations

import os
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from seehere.api.errors import APIError
from seehere.api.jobs import require_app_request
from seehere.api.projects import _header_text
from seehere.api.uploads import Received, receive_upload
from seehere.core.config import Settings, get_settings
from seehere.db.enums import MediaKind
from seehere.db.models import Frame, MediaAsset, Project, Slide
from seehere.db.session import get_db
from seehere.jobs import queue
from seehere.media.storage import MediaStore, project_dir, sanitize_filename
from seehere.slides.deck import DeckRejected, DeckType, identify_deck
from seehere.slides.ingest import queue_deck_ingest

router = APIRouter(prefix="/api", tags=["deck"])

DbDep = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


class SlidePage(BaseModel):
    page: int
    text: str
    frame_id: uuid.UUID | None  # keyframe where this page appears, if aligned
    t_s: float | None
    score: float | None  # text similarity with that keyframe (0..1)


class DeckOut(BaseModel):
    available: bool  # a deck has been uploaded
    filename: str | None = None
    kind: str | None = None
    ingested: bool = False  # its pages have been read
    pages: list[SlidePage] = []


def _project_or_404(db: Session, project_id: uuid.UUID) -> None:
    if db.get(Project, project_id) is None:
        raise APIError(404, "not_found", "No project with this ID.")


@router.post(
    "/projects/{project_id}/deck",
    status_code=201,
    response_model=DeckOut,
    dependencies=[Depends(require_app_request)],
)
async def upload_deck(
    project_id: uuid.UUID,
    request: Request,
    settings: SettingsDep,
    db: DbDep,
    x_seehere_filename: Annotated[str | None, Header()] = None,
) -> DeckOut:
    await run_in_threadpool(_project_or_404, db, project_id)
    filename = sanitize_filename(_header_text(x_seehere_filename, "X-SeeHere-Filename"))
    store = MediaStore(settings.media_dir)
    upload = await receive_upload(request, store, settings.max_deck_bytes, settings.max_deck_mb)
    try:
        try:
            deck = await run_in_threadpool(identify_deck, upload.path)
        except DeckRejected as exc:
            raise APIError(415, "unsupported_deck", exc.message) from exc
        await run_in_threadpool(_replace_deck, db, store, project_id, upload, filename, deck)
    finally:
        await run_in_threadpool(lambda: upload.path.unlink(missing_ok=True))
    return await run_in_threadpool(get_deck, project_id, db)


def _replace_deck(
    db: Session,
    store: MediaStore,
    project_id: uuid.UUID,
    upload: Received,
    filename: str,
    deck: DeckType,
) -> None:
    old = db.scalars(
        select(MediaAsset).where(
            MediaAsset.project_id == project_id, MediaAsset.kind == MediaKind.SLIDE_DECK
        )
    ).first()
    old_path = old.storage_path if old else None
    if old is not None:
        db.execute(delete(MediaAsset).where(MediaAsset.id == old.id))  # slides cascade
    relative = f"{project_dir(project_id)}/deck-{uuid.uuid4().hex[:8]}{deck.extension}"
    db.add(
        MediaAsset(
            project_id=project_id,
            kind=MediaKind.SLIDE_DECK,
            original_filename=filename,
            storage_path=relative,
            mime_type=deck.mime_type,
            size_bytes=upload.size,
            sha256=upload.sha256,
        )
    )
    queue_deck_ingest(db, project_id)
    dest = store.promote(upload.path, relative)
    os.chmod(dest, 0o600)
    try:
        db.commit()
    except Exception:
        store.remove(relative)
        raise
    if old_path and old_path != relative:
        store.remove(old_path)
    queue.refresh_project_status(db, project_id)


@router.get("/projects/{project_id}/deck", response_model=DeckOut)
def get_deck(project_id: uuid.UUID, db: DbDep) -> DeckOut:
    _project_or_404(db, project_id)
    deck = db.scalars(
        select(MediaAsset).where(
            MediaAsset.project_id == project_id, MediaAsset.kind == MediaKind.SLIDE_DECK
        )
    ).first()
    if deck is None:
        return DeckOut(available=False)
    rows = db.execute(
        select(Slide, Frame.t_s)
        .outerjoin(Frame, Slide.aligned_frame_id == Frame.id)
        .where(Slide.media_asset_id == deck.id)
        .order_by(Slide.page_number)
    ).all()
    return DeckOut(
        available=True,
        filename=deck.original_filename,
        kind="pdf" if deck.storage_path.endswith(".pdf") else "pptx",
        ingested=bool(deck.probe and "pages" in deck.probe),
        pages=[
            SlidePage(
                page=slide.page_number,
                text=slide.text,
                frame_id=slide.aligned_frame_id,
                t_s=t_s,
                score=slide.alignment_score,
            )
            for slide, t_s in rows
        ],
    )
