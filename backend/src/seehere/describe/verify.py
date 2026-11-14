"""Claim verification (Task 17): check every claim in a cue against its own evidence.

Claims come from all three wordings:
  quote        text in “…” must appear in the OCR text of the cue's region or its deck page
  number       every number must appear, with the same value, on screen or on the deck page
  description  any other statement ("Chart: …", a vision model's details) cannot be checked
               against text; it is supported only by a vision model having seen the frame

Each check yields a state, and the cue takes the weakest:
  verified_text_match  found as written in OCR text (OCR line confidence >= 0.6) or the deck
  corroborated         a description backed by a vision model's view of the keyframe
  uncertain            found only after repairing OCR digits, or in a low-confidence OCR line
  needs_review         not found in the evidence, or a statement nothing supports
OCR can misread, so a text match shows the words are on screen, not that a description of
their meaning is right.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from seehere.db.enums import CheckResult, VerificationState
from seehere.db.models import (
    DescriptionCue,
    OcrRegion,
    Slide,
    VerificationEvent,
    VisualUnit,
)
from seehere.jobs import queue
from seehere.jobs.queue import ClaimedJob
from seehere.jobs.worker import JobContext
from seehere.schedule.plan import queue_schedule
from seehere.text.numbers import NumberMention, extract_numbers, fix_ocr_digits
from seehere.text.words import content_words

log = logging.getLogger("seehere.verify")

JOB_KIND = "claims.verify"
LOW_OCR_CONFIDENCE = 0.6
OCR_SOURCE = "ocr"

# Weakest first: a cue takes the weakest state of its claims.
STRENGTH = [
    VerificationState.NEEDS_REVIEW,
    VerificationState.UNCERTAIN,
    VerificationState.CORROBORATED,
    VerificationState.VERIFIED_TEXT_MATCH,
]
_QUOTE = re.compile(r"“([^”]*)”")
_FIXED = re.compile(r"\b(On screen|Chart|Table|Diagram|Equation|Image)\s*:", re.IGNORECASE)


@dataclass(frozen=True)
class OcrLine:
    text: str
    confidence: float


@dataclass
class Sources:
    """The text a cue's evidence offers to check claims against."""

    ocr: list[OcrLine] = field(default_factory=list)
    slides: list[str] = field(default_factory=list)
    seen_by_model: bool = False  # a vision model described the keyframe


@dataclass(frozen=True)
class Check:
    claim: str
    name: str  # quote_match, number_match, description_support
    result: CheckResult
    state: VerificationState
    detail: dict[str, Any]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip(" .,;:!?")


def _claims(texts: list[str]) -> tuple[list[str], list[NumberMention], list[str]]:
    quotes: list[str] = []
    numbers: dict[str, NumberMention] = {}
    statements: list[str] = []
    for text in texts:
        for q in _QUOTE.findall(text):
            if q not in quotes:
                quotes.append(q)
        for n in extract_numbers(text):
            numbers.setdefault(n.raw, n)
        rest = _FIXED.sub(" ", _QUOTE.sub(" ", text))
        for sentence in re.split(r"(?<=[.!?])\s+", rest):
            s = sentence.strip(" .")
            if content_words(s) and s not in statements:
                statements.append(s)
    return quotes, list(numbers.values()), statements


def check_quote(quote: str, src: Sources) -> Check:
    truncated = quote.endswith("…")
    q = _norm(quote.rstrip("…"))
    for line in src.ocr:
        if q and q in _norm(line.text) and (truncated or len(q) >= len(_norm(line.text)) * 0.5):
            if line.confidence < LOW_OCR_CONFIDENCE:
                return Check(
                    quote,
                    "quote_match",
                    CheckResult.INCONCLUSIVE,
                    VerificationState.UNCERTAIN,
                    {"source": "ocr", "ocr_confidence": line.confidence},
                )
            return Check(
                quote,
                "quote_match",
                CheckResult.PASS,
                VerificationState.VERIFIED_TEXT_MATCH,
                {"source": "ocr", "ocr_confidence": line.confidence},
            )
    if any(q in _norm(s) for s in src.slides):
        return Check(
            quote,
            "quote_match",
            CheckResult.PASS,
            VerificationState.VERIFIED_TEXT_MATCH,
            {"source": "slide"},
        )
    return Check(
        quote,
        "quote_match",
        CheckResult.FAIL,
        VerificationState.NEEDS_REVIEW,
        {"reason": "not found in the text read on screen or on the deck page"},
    )


def _same(a: NumberMention, b: NumberMention) -> bool:
    return a.value == b.value and a.percent == b.percent


def check_number(n: NumberMention, src: Sources) -> Check:
    for line in src.ocr:
        if any(_same(n, m) for m in extract_numbers(line.text)):
            low = line.confidence < LOW_OCR_CONFIDENCE
            return Check(
                n.raw,
                "number_match",
                CheckResult.INCONCLUSIVE if low else CheckResult.PASS,
                VerificationState.UNCERTAIN if low else VerificationState.VERIFIED_TEXT_MATCH,
                {"source": "ocr", "ocr_confidence": line.confidence},
            )
    if any(_same(n, m) for s in src.slides for m in extract_numbers(s)):
        return Check(
            n.raw,
            "number_match",
            CheckResult.PASS,
            VerificationState.VERIFIED_TEXT_MATCH,
            {"source": "slide"},
        )
    for line in src.ocr:  # only after reading "1O0" as "100": the screen may say otherwise
        if any(_same(n, m) for m in extract_numbers(fix_ocr_digits(line.text))):
            return Check(
                n.raw,
                "number_match",
                CheckResult.INCONCLUSIVE,
                VerificationState.UNCERTAIN,
                {"source": "ocr", "repaired": True, "ocr_text": line.text},
            )
    return Check(
        n.raw,
        "number_match",
        CheckResult.FAIL,
        VerificationState.NEEDS_REVIEW,
        {"reason": "this value does not appear on screen or on the deck page"},
    )


def check_statement(statement: str, src: Sources) -> Check:
    if src.seen_by_model:
        return Check(
            statement,
            "description_support",
            CheckResult.INCONCLUSIVE,
            VerificationState.CORROBORATED,
            {"source": "vision model on the keyframe"},
        )
    return Check(
        statement,
        "description_support",
        CheckResult.FAIL,
        VerificationState.NEEDS_REVIEW,
        {"reason": "no evidence describes this; only text was read on screen"},
    )


def verify_texts(texts: list[str], src: Sources) -> tuple[VerificationState, list[Check]]:
    quotes, numbers, statements = _claims(texts)
    checks = (
        [check_quote(q, src) for q in quotes]
        + [check_number(n, src) for n in numbers]
        + [check_statement(s, src) for s in statements]
    )
    if not checks:
        return VerificationState.NEEDS_REVIEW, []
    return min((c.state for c in checks), key=STRENGTH.index), checks


def _sources(s: Session, cue: DescriptionCue) -> Sources:
    src = Sources()
    region_ids = [e.ocr_region_id for e in cue.evidence if e.ocr_region_id]
    slide_ids = [e.slide_id for e in cue.evidence if e.slide_id]
    unit_ids = [e.visual_unit_id for e in cue.evidence if e.visual_unit_id]
    if region_ids:
        src.ocr = [
            OcrLine(r.text, r.confidence)
            for r in s.scalars(select(OcrRegion).where(OcrRegion.id.in_(region_ids)))
        ]
    if slide_ids:
        src.slides = list(s.scalars(select(Slide.text).where(Slide.id.in_(slide_ids))))
    if unit_ids:
        sources = s.scalars(select(VisualUnit.source).where(VisualUnit.id.in_(unit_ids)))
        src.seen_by_model = any(name != OCR_SOURCE for name in sources)
    return src


def queue_verification(session: Session, project_id: uuid.UUID) -> None:
    """Queue (or re-queue) after cues were written. Does not commit."""
    queue.enqueue_or_restart(
        session, project_id=project_id, kind=JOB_KIND, idempotency_key=f"{JOB_KIND}:{project_id}"
    )


def verify_claims(ctx: JobContext, job: ClaimedJob) -> None:
    with ctx.session() as s:
        cues = list(
            s.scalars(
                select(DescriptionCue)
                .where(DescriptionCue.project_id == job.project_id)
                .options(selectinload(DescriptionCue.evidence))
            )
        )
        s.execute(
            delete(VerificationEvent).where(VerificationEvent.cue_id.in_([c.id for c in cues]))
        )
        counts: dict[VerificationState, int] = dict.fromkeys(VerificationState, 0)
        for n, cue in enumerate(cues):
            ctx.progress("verify", n / max(1, len(cues)))
            texts = [t for t in (cue.text_short, cue.text_medium, cue.text_long) if t]
            state, checks = verify_texts(texts, _sources(s, cue))
            cue.verification_state = state
            counts[state] += 1
            s.add_all(
                VerificationEvent(
                    cue_id=cue.id,
                    claim=c.claim,
                    check_name=c.name,
                    result=c.result,
                    resulting_state=c.state,
                    detail=c.detail,
                )
                for c in checks
            )
        ctx.check_cancelled()
        queue_schedule(s, job.project_id)
        s.commit()
    log.info("project %s: verified %d cues %s", job.project_id, len(cues), counts)
    ctx.progress("verify", 1.0)
