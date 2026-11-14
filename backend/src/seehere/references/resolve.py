"""Visual reference resolution (Task 14): link spoken pointers ("this blue line here") to the
visual unit on screen they most likely mean, or flag them for review instead of guessing.

Detection is rule-based and conservative: a demonstrative followed (within three words) by a
visual noun ("this chart", "these two bars"), a generic noun with "here/there" ("this one
here"), or a bare pointer ("right here", "as you can see").

Each unit on screen when the phrase starts is scored on three kinds of evidence:
  words   the phrase and the next few seconds of speech share words or numbers with the unit
  kind    the noun names the unit's kind ("table" -> a table)
  place   a position word ("on the left", in the phrase or just after) matches its box
combined as independent evidence (1 - product of misses); a stated place that does not match
cuts a unit's score to 30%. A lone candidate starts from 0.5; with several, confidence is the
lead of the best over the runner-up, so two equally good matches give 0 and are flagged as
ambiguous, never guessed.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from seehere.db.enums import MediaKind, ReferenceStatus, VisualKind
from seehere.db.models import MediaAsset, ReferenceLink, TranscriptWord, VisualUnit
from seehere.describe.generate import queue_descriptions
from seehere.jobs import queue
from seehere.jobs.queue import ClaimedJob
from seehere.jobs.worker import JobContext
from seehere.text.numbers import extract_numbers, fix_ocr_digits, same_number
from seehere.text.words import content_words, join_words, spoken_numbers, stem

log = logging.getLogger("seehere.references")

JOB_KIND = "references.resolve"
CONTEXT_S = 4.0  # speech after the phrase that may say what it points at
APPEAR_LEAD_S = 0.5  # "this slide" said just before the slide appears
MAX_MODIFIERS = 3
PLACE_LOOKAHEAD = 4  # "this chart on the right": position words just after the phrase

DEMONSTRATIVES = {"this", "that", "these", "those"}
POINTERS = {"here", "there"}
POINTER_LEADS = {"over", "right", "up", "down"}
# Nouns that name something visual, with the kinds they suggest (empty: any kind).
VISUAL_NOUNS: dict[str, set[VisualKind]] = {
    **dict.fromkeys(
        ["chart", "graph", "plot", "bar", "line", "curve", "axis", "slope", "peak", "trend"],
        {VisualKind.CHART},
    ),
    **dict.fromkeys(["table", "row", "column", "cell"], {VisualKind.TABLE}),
    **dict.fromkeys(["equation", "formula", "term", "expression"], {VisualKind.EQUATION}),
    **dict.fromkeys(["diagram", "arrow", "box", "circle", "node"], {VisualKind.DIAGRAM}),
    **dict.fromkeys(["picture", "image", "photo"], {VisualKind.IMAGE}),
    **dict.fromkeys(
        ["title", "heading", "bullet", "text", "word", "label"], {VisualKind.TEXT_BLOCK}
    ),
    **dict.fromkeys(["number", "value", "figure", "percentage", "slide", "region"], set()),
}
# Too vague alone ("that one", "this part" of the argument): only with "here"/"there".
GENERIC_NOUNS = {"one", "part", "bit", "area", "thing"}
POSITIONS = {"left", "right", "top", "bottom", "middle", "center", "centre"}
NOT_CUES = DEMONSTRATIVES | POINTERS | POINTER_LEADS | GENERIC_NOUNS | POSITIONS


@dataclass(frozen=True)
class Word:
    id: uuid.UUID
    start_s: float
    text: str

    @property
    def token(self) -> str:
        return re.sub(r"[^a-z0-9.%]", "", self.text.lower()).strip(".")


@dataclass(frozen=True)
class Phrase:
    start: int  # word positions, inclusive
    end: int
    noun: str | None  # the visual noun, if any

    def text(self, words: list[Word]) -> str:
        return " ".join(w.text for w in words[self.start : self.end + 1]).strip(" ,.;:!?")


def detect_phrases(words: list[Word]) -> list[Phrase]:
    tokens = [w.token for w in words]
    found: list[Phrase] = []
    i = 0
    while i < len(tokens):
        phrase = _phrase_at(tokens, i)
        if phrase:
            found.append(phrase)
            i = phrase.end + 1
        else:
            i += 1
    return found


def _phrase_at(tokens: list[str], i: int) -> Phrase | None:
    t = tokens[i]
    if t in DEMONSTRATIVES:
        for j in range(i + 1, min(len(tokens), i + 2 + MAX_MODIFIERS)):
            noun = stem(tokens[j])
            if noun in VISUAL_NOUNS or noun in GENERIC_NOUNS:
                end = j + 1 if j + 1 < len(tokens) and tokens[j + 1] in POINTERS else j
                if noun in GENERIC_NOUNS and end == j:
                    return None  # "that one" alone is not a pointer
                return Phrase(i, end, noun)
            if tokens[j] in DEMONSTRATIVES or not tokens[j].isalpha():
                return None
        return None
    if t in POINTER_LEADS and i + 1 < len(tokens) and tokens[i + 1] in POINTERS:
        return Phrase(i, i + 1, None)
    if tokens[i : i + 4] == ["as", "you", "can", "see"]:
        return Phrase(i, i + 3, None)
    return None


@dataclass(frozen=True)
class Candidate:
    id: uuid.UUID
    kind: VisualKind
    text: str  # label, lines and details
    t_start_s: float
    t_end_s: float
    box: tuple[float, float, float, float] | None


@dataclass(frozen=True)
class Resolution:
    unit_id: uuid.UUID | None
    confidence: float
    status: ReferenceStatus
    scores: dict[uuid.UUID, float]


def _position_match(words: set[str], box: tuple[float, float, float, float] | None) -> float:
    wanted = words & POSITIONS
    if not wanted or box is None:
        return 0.0
    cx, cy = box[0] + box[2] / 2, box[1] + box[3] / 2
    checks = {
        "left": cx < 0.4,
        "right": cx > 0.6,
        "top": cy < 0.4,
        "bottom": cy > 0.6,
        "middle": 0.3 <= cx <= 0.7 and 0.3 <= cy <= 0.7,
    }
    checks["center"] = checks["centre"] = checks["middle"]
    return sum(checks[w] for w in wanted) / len(wanted)


def score_candidate(
    c: Candidate, noun: str | None, cue_words: set[str], cue_numbers: list[Decimal], place: set[str]
) -> float:
    unit_words = content_words(c.text)
    shown_numbers = extract_numbers(fix_ocr_digits(c.text))
    hits = len(cue_words & unit_words) + 2 * sum(
        any(same_number(n, v) for v in cue_numbers) for n in shown_numbers
    )
    lexical = min(1.0, hits / 2)
    kind = 1.0 if c.kind in VISUAL_NOUNS.get(noun or "", set()) else 0.0
    position = _position_match(place, c.box)
    score = 1 - (1 - 0.9 * lexical) * (1 - 0.6 * kind) * (1 - 0.5 * position)
    if place & POSITIONS and position == 0:
        score *= 0.3  # said "on the left", but this is not on the left
    return round(score, 4)


def resolve(
    phrase_text: str,
    context_text: str,
    noun: str | None,
    candidates: list[Candidate],
    threshold: float,
) -> Resolution:
    if not candidates:
        return Resolution(None, 0.0, ReferenceStatus.UNRESOLVED, {})
    place_words = re.findall(r"[a-z]+", context_text.lower())[:PLACE_LOOKAHEAD]
    raw = set(re.findall(r"[a-z]+", phrase_text.lower())) | set(place_words)
    cue_words = content_words(f"{phrase_text} {context_text}") - {stem(w) for w in NOT_CUES}
    cue_numbers = spoken_numbers(context_text) + spoken_numbers(phrase_text)
    scores = {c.id: score_candidate(c, noun, cue_words, cue_numbers, raw) for c in candidates}
    ranked = sorted(candidates, key=lambda c: -scores[c.id])
    best = scores[ranked[0].id]
    confidence = 0.5 + 0.5 * best if len(ranked) == 1 else best - scores[ranked[1].id]
    confidence = round(min(1.0, max(0.0, confidence)), 4)
    if confidence >= threshold:
        return Resolution(ranked[0].id, confidence, ReferenceStatus.LINKED, scores)
    # Below the threshold nothing is linked: a reviewer decides (NEEDS REVIEW).
    return Resolution(None, confidence, ReferenceStatus.AMBIGUOUS, scores)


def queue_references(session: Session, project_id: uuid.UUID) -> None:
    """Queue (or re-queue) after the units were scored. Does not commit."""
    queue.enqueue_or_restart(
        session, project_id=project_id, kind=JOB_KIND, idempotency_key=f"{JOB_KIND}:{project_id}"
    )


def _candidates(units: list[VisualUnit]) -> list[Candidate]:
    out = []
    for u in units:
        text = "\n".join([u.label, *u.values.get("lines", []), u.values.get("details", "")])
        box = (u.x, u.y, u.w, u.h)
        out.append(
            Candidate(
                u.id,
                u.kind,
                text,
                u.t_start_s,
                u.t_end_s,
                box if None not in box else None,  # type: ignore[arg-type]
            )
        )
    return out


def resolve_references(ctx: JobContext, job: ClaimedJob) -> None:
    with ctx.session() as s:
        units = list(s.scalars(select(VisualUnit).where(VisualUnit.project_id == job.project_id)))
        audio_id = s.scalar(
            select(MediaAsset.id).where(
                MediaAsset.project_id == job.project_id,
                MediaAsset.kind == MediaKind.NORMALIZED_AUDIO,
            )
        )
        words = [
            Word(w.id, w.start_s, w.text)
            for w in s.scalars(
                select(TranscriptWord)
                .where(TranscriptWord.media_asset_id == audio_id)
                .order_by(TranscriptWord.idx)
            )
        ]
        candidates = _candidates(units)
        links = []
        for n, p in enumerate(detect_phrases(words)):
            ctx.progress("resolve", n / max(1, len(words)))
            t = words[p.start].start_s
            end_t = words[p.end].start_s
            context = join_words(
                [w.text for w in words[p.end + 1 :] if w.start_s <= end_t + CONTEXT_S]
            )
            on_screen = [c for c in candidates if c.t_start_s - APPEAR_LEAD_S <= t < c.t_end_s]
            r = resolve(
                p.text(words), context, p.noun, on_screen, ctx.settings.reference_link_threshold
            )
            links.append(
                ReferenceLink(
                    project_id=job.project_id,
                    phrase=p.text(words),
                    start_word_id=words[p.start].id,
                    end_word_id=words[p.end].id,
                    t_s=t,
                    visual_unit_id=r.unit_id,
                    confidence=r.confidence,
                    status=r.status,
                )
            )
        ctx.check_cancelled()
        s.execute(delete(ReferenceLink).where(ReferenceLink.project_id == job.project_id))
        s.add_all(links)
        queue_descriptions(s, job.project_id)
        s.commit()
    by_status = {st: sum(lk.status == st for lk in links) for st in ReferenceStatus}
    log.info("project %s: references %s", job.project_id, by_status)
    ctx.progress("resolve", 1.0)
