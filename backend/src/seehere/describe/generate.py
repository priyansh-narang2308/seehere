"""Description writing (Task 16): one cue per visual unit that was not fully said aloud, in
short, medium and long wordings, each with its evidence ledger (Task 15).

Wordings are assembled from the unit's own fields only (its label, the lines read on screen,
and a vision model's details when there are any). Nothing is paraphrased or added, so every
value in a cue appears in its evidence; claim verification (Task 17) checks that. Text read on
screen is quoted as it was read. A cue starts as NEEDS REVIEW.

A slide shown more than once is described at its first appearance that was not fully said.
A unit the speaker pointed at ("this line here", linked in Task 14) is anchored at that moment
and its priority is raised, since the listener was told to look at it.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from seehere.db.enums import EvidenceKind, MediaKind, ReferenceStatus, VisualKind
from seehere.db.models import (
    DescriptionCue,
    Evidence,
    MediaAsset,
    OcrRegion,
    ReferenceLink,
    Slide,
    TranscriptWord,
    VisualUnit,
)
from seehere.describe.carryover import remember_reviews, restore_reviews
from seehere.describe.verify import queue_verification
from seehere.jobs import queue
from seehere.jobs.queue import ClaimedJob
from seehere.jobs.worker import JobContext

log = logging.getLogger("seehere.describe")

JOB_KIND = "descriptions.generate"
MAX_QUOTE_WORDS = 15
MEDIUM_LINES = 3
LONG_LINES = 6
POINTED_AT_BOOST = 0.2

KIND_NAME = {
    VisualKind.CHART: "Chart",
    VisualKind.TABLE: "Table",
    VisualKind.DIAGRAM: "Diagram",
    VisualKind.EQUATION: "Equation",
    VisualKind.IMAGE: "Image",
}


def quote(line: str) -> str:
    """A line as read, in quotes; very long lines are cut at a word boundary."""
    words = line.strip().split()
    cut = " ".join(words[:MAX_QUOTE_WORDS]) + ("…" if len(words) > MAX_QUOTE_WORDS else "")
    return f"“{cut.rstrip(' .,;:')}”"


@dataclass(frozen=True)
class Wordings:
    short: str
    medium: str | None
    long: str | None


def write_wordings(kind: VisualKind, label: str, lines: list[str], details: str) -> Wordings:
    lines = [ln for ln in (ln.strip() for ln in lines) if ln] or [label]
    name = KIND_NAME.get(kind)
    if name:  # a chart, table... named by its label, then the text read inside it
        head = f"{name}: {label.rstrip('. ')}."
        body = lines if lines != [label] else []
    else:  # text on screen: the lines themselves
        head = f"On screen: {quote(lines[0])}."
        body = lines[1:]
    medium_body = body[: MEDIUM_LINES - 1]
    medium = " ".join([head, *(f"{quote(ln)}." for ln in medium_body)])
    long_parts = [head]
    if details:
        long_parts.append(details.strip().rstrip(".") + ".")
    long_parts += [f"{quote(ln)}." for ln in body[: LONG_LINES - 1]]
    long = " ".join(long_parts)
    return Wordings(head, medium if medium != head else None, long if long != medium else None)


def queue_descriptions(session: Session, project_id: uuid.UUID) -> None:
    """Queue (or re-queue) after references were resolved. Does not commit."""
    queue.enqueue_or_restart(
        session, project_id=project_id, kind=JOB_KIND, idempotency_key=f"{JOB_KIND}:{project_id}"
    )


def _inside(region: OcrRegion, unit: VisualUnit) -> bool:
    if None in (unit.x, unit.y, unit.w, unit.h):
        return False
    cx, cy = region.x + region.w / 2, region.y + region.h / 2
    return bool(unit.x <= cx <= unit.x + unit.w and unit.y <= cy <= unit.y + unit.h)  # type: ignore[operator]


def _evidence(
    s: Session,
    unit: VisualUnit,
    links: list[ReferenceLink],
    words: list[tuple[uuid.UUID, float]],
) -> list[Evidence]:
    out = [
        Evidence(kind=EvidenceKind.VISUAL_UNIT, visual_unit_id=unit.id, note=f"{unit.source} unit"),
        Evidence(kind=EvidenceKind.FRAME, frame_id=unit.frame_id, note="keyframe"),
    ]
    for r in s.scalars(select(OcrRegion).where(OcrRegion.frame_id == unit.frame_id)):
        if _inside(r, unit):
            out.append(Evidence(kind=EvidenceKind.OCR_REGION, ocr_region_id=r.id, note="text read"))
    for slide in s.scalars(select(Slide).where(Slide.aligned_frame_id == unit.frame_id)):
        out.append(
            Evidence(
                kind=EvidenceKind.SLIDE, slide_id=slide.id, note=f"deck page {slide.page_number}"
            )
        )
    for link in links:
        out.append(
            Evidence(
                kind=EvidenceKind.TRANSCRIPT_SPAN,
                start_word_id=link.start_word_id,
                end_word_id=link.end_word_id,
                note=f"spoken reference: {link.phrase}",
            )
        )
    shown = [wid for wid, t in words if unit.t_start_s <= t < unit.t_end_s]
    if shown:
        out.append(
            Evidence(
                kind=EvidenceKind.TRANSCRIPT_SPAN,
                start_word_id=shown[0],
                end_word_id=shown[-1],
                note="speech while shown",
            )
        )
    return out


def generate_descriptions(ctx: JobContext, job: ClaimedJob) -> None:
    pid = job.project_id
    with ctx.session() as s:
        units = list(
            s.scalars(
                select(VisualUnit)
                .where(VisualUnit.project_id == pid)
                .order_by(VisualUnit.t_start_s, VisualUnit.y)
            )
        )
        links: dict[uuid.UUID, list[ReferenceLink]] = {}
        for link in s.scalars(
            select(ReferenceLink)
            .where(ReferenceLink.project_id == pid, ReferenceLink.status == ReferenceStatus.LINKED)
            .order_by(ReferenceLink.t_s)
        ):
            links.setdefault(link.visual_unit_id, []).append(link)  # type: ignore[arg-type]
        audio_id = s.scalar(
            select(MediaAsset.id).where(
                MediaAsset.project_id == pid, MediaAsset.kind == MediaKind.NORMALIZED_AUDIO
            )
        )
        words = [
            (w.id, w.start_s)
            for w in s.execute(
                select(TranscriptWord.id, TranscriptWord.start_s)
                .where(TranscriptWord.media_asset_id == audio_id)
                .order_by(TranscriptWord.idx)
            )
        ]

        kept = remember_reviews(s, pid)
        s.execute(delete(DescriptionCue).where(DescriptionCue.project_id == pid))
        described: set[tuple[uuid.UUID, str]] = set()
        cues = []
        for n, u in enumerate(units):
            ctx.progress("write", n / max(1, len(units)))
            if (u.coverage_score or 0.0) >= 1.0 or (u.frame_id, u.label) in described:
                continue  # fully said aloud, or already described at an earlier appearance
            described.add((u.frame_id, u.label))
            w = write_wordings(
                u.kind, u.label, u.values.get("lines", []), u.values.get("details", "")
            )
            pointed = links.get(u.id, [])
            cue = DescriptionCue(
                project_id=pid,
                visual_unit_id=u.id,
                text_short=w.short,
                text_medium=w.medium,
                text_long=w.long,
                anchor_t_s=pointed[0].t_s if pointed else u.t_start_s,
                priority=round(
                    min(1.0, (u.priority or 0.0) + (POINTED_AT_BOOST if pointed else 0)), 4
                ),
            )
            cue.evidence = _evidence(s, u, pointed, words)
            cues.append(cue)
        ctx.check_cancelled()
        s.add_all(cues)
        s.flush()
        restored = restore_reviews(s, cues, {u.id: u for u in units}, kept)
        queue_verification(s, pid)
        s.commit()
    log.info(
        "project %s: %d description cues from %d units, %d reviews kept",
        pid,
        len(cues),
        len(units),
        restored,
    )
    ctx.progress("write", 1.0)
