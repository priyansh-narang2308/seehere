"""Job `deck.ingest`: read the uploaded deck's pages and align them to keyframes.

Runs when a deck is uploaded, and again whenever on-screen text is re-read (Task 10), since
alignment compares page text with keyframe OCR text. Before OCR has run, pages are stored
unaligned. Idempotent: a run replaces all `slide` rows of the deck.
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from seehere.db.enums import JobStatus, MediaKind
from seehere.db.models import Frame, Job, MediaAsset, OcrRegion, Slide
from seehere.jobs import queue
from seehere.jobs.errors import PermanentJobError
from seehere.jobs.queue import ClaimedJob
from seehere.jobs.worker import JobContext
from seehere.slides.deck import DeckRejected, align, extract_pages, identify_deck

log = logging.getLogger("seehere.slides")

JOB_KIND = "deck.ingest"
OCR_JOB_KIND = "ocr.extract"  # see seehere.media.ocr (not imported: it imports this module)


def queue_deck_ingest(session: Session, project_id: uuid.UUID) -> None:
    """Queue (or re-queue) deck ingestion. Does not commit."""
    queue.enqueue_or_restart(
        session, project_id=project_id, kind=JOB_KIND, idempotency_key=f"{JOB_KIND}:{project_id}"
    )


def has_deck(session: Session, project_id: uuid.UUID) -> bool:
    return (
        session.scalar(
            select(MediaAsset.id).where(
                MediaAsset.project_id == project_id, MediaAsset.kind == MediaKind.SLIDE_DECK
            )
        )
        is not None
    )


def _keyframe_text(session: Session, project_id: uuid.UUID) -> list[tuple[uuid.UUID, str]]:
    """Keyframes with their OCR text, or [] if text recognition has not finished."""
    ocr_done = session.scalar(
        select(Job.id).where(
            Job.project_id == project_id,
            Job.kind == OCR_JOB_KIND,
            Job.status == JobStatus.SUCCEEDED,
        )
    )
    if ocr_done is None:
        return []
    frames = list(
        session.scalars(
            select(Frame.id)
            .join(MediaAsset, Frame.media_asset_id == MediaAsset.id)
            .where(
                MediaAsset.project_id == project_id,
                MediaAsset.kind == MediaKind.SOURCE_VIDEO,
                Frame.is_keyframe.is_(True),
            )
            .order_by(Frame.t_s)
        )
    )
    text: dict[uuid.UUID, list[str]] = defaultdict(list)
    for frame_id, line in session.execute(
        select(OcrRegion.frame_id, OcrRegion.text)
        .where(OcrRegion.frame_id.in_(frames))
        .order_by(OcrRegion.y, OcrRegion.x)
    ):
        text[frame_id].append(line)
    return [(f, "\n".join(text[f])) for f in frames]


def ingest_deck(ctx: JobContext, job: ClaimedJob) -> None:
    with ctx.session() as s:
        deck = s.scalars(
            select(MediaAsset).where(
                MediaAsset.project_id == job.project_id, MediaAsset.kind == MediaKind.SLIDE_DECK
            )
        ).first()
        if deck is None:
            raise PermanentJobError("No slide deck has been added to this project.")
        deck_id, rel = deck.id, deck.storage_path
        screens = _keyframe_text(s, job.project_id)

    path = ctx.store.resolve(rel)
    ctx.progress("read", 0.0)
    try:
        pages = extract_pages(path, identify_deck(path))
    except DeckRejected as exc:
        raise PermanentJobError(exc.message) from exc
    except OSError as exc:
        raise PermanentJobError("The slide deck file is missing from storage.") from exc

    ctx.progress("align", 0.6)
    alignments = align(pages, [t for _, t in screens], ctx.settings.slide_align_threshold)
    ctx.check_cancelled()
    with ctx.session() as s:
        s.execute(delete(Slide).where(Slide.media_asset_id == deck_id))
        s.add_all(
            Slide(
                media_asset_id=deck_id,
                page_number=n,
                text=text,
                aligned_frame_id=screens[a.frame_index][0] if a.frame_index is not None else None,
                alignment_score=a.score if screens else None,
            )
            for n, (text, a) in enumerate(zip(pages, alignments, strict=True), start=1)
        )
        asset = s.get(MediaAsset, deck_id)
        if asset is not None:
            asset.probe = {
                "pages": len(pages),
                "aligned": sum(a.frame_index is not None for a in alignments),
                "ocr_available": bool(screens),
            }
        s.commit()
    log.info(
        "project %s: deck with %d pages, %d aligned",
        job.project_id,
        len(pages),
        sum(a.frame_index is not None for a in alignments),
    )
    ctx.progress("save", 1.0)
