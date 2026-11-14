"""Seen versus said (Task 13): how much of each visual unit the speaker already said aloud.

For each unit, the transcript words spoken from `pad` seconds before it appears until `pad`
seconds after it leaves are compared with the unit's text. Coverage is the share of its
distinctive words and numbers that were spoken; numbers count double, because a missed value
matters more than a missed word. A number counts as said when a spoken value agrees with it
within the rounding shown (`same_number`), whether spoken as digits or as words.

priority = (1 - coverage) x weight of the unit's kind: what is shown but not said comes first.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from seehere.db.enums import MediaKind, VisualKind
from seehere.db.models import MediaAsset, TranscriptWord, VisualUnit
from seehere.jobs import queue
from seehere.jobs.queue import ClaimedJob
from seehere.jobs.worker import JobContext
from seehere.text.numbers import extract_numbers, fix_ocr_digits, same_number, words_to_number

log = logging.getLogger("seehere.coverage")

JOB_KIND = "coverage.score"
NUMBER_WEIGHT = 2
MAX_NUMBER_WORDS = 8

KIND_WEIGHT = {
    VisualKind.CHART: 1.0,
    VisualKind.TABLE: 1.0,
    VisualKind.DIAGRAM: 0.9,
    VisualKind.EQUATION: 0.9,
    VisualKind.IMAGE: 0.7,
    VisualKind.TEXT_BLOCK: 0.6,
    VisualKind.OTHER: 0.5,
}

_WORD = re.compile(r"[a-z]+")
_STOP_WORDS = (
    "the and for are but not you all any can had her was one our out has have this that with "
    "from they will would there their what which when your into than then them these those "
    "its also been more most some such only over very just about"
)
_STOP = frozenset(_STOP_WORDS.split())


def _stem(word: str) -> str:
    for suffix in ("ies", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)] + ("y" if suffix == "ies" else "")
    return word


def content_words(text: str) -> set[str]:
    """Distinctive words: 3+ letters, not a stop word, plural folded."""
    return {_stem(w) for w in _WORD.findall(text.lower()) if len(w) >= 3 and w not in _STOP}


def spoken_numbers(text: str) -> list[Decimal]:
    """Values said as digits ("12.5") or as words ("twelve point five")."""
    values = [m.value for m in extract_numbers(text)]
    words = _WORD.findall(text.lower())
    i = 0
    while i < len(words):
        # the longest run of words starting here that reads as one number
        for j in range(min(len(words), i + MAX_NUMBER_WORDS), i, -1):
            value = words_to_number(" ".join(words[i:j]))
            if value is not None:
                values.append(value)
                i = j
                break
        else:
            i += 1
    return values


@dataclass(frozen=True)
class Score:
    coverage: float
    priority: float
    said: list[str]
    unsaid: list[str]


def score_unit(kind: VisualKind, shown_text: str, spoken_text: str) -> Score:
    shown = fix_ocr_digits(shown_text)
    numbers = extract_numbers(shown)
    # numbers are matched by value, so drop their digits from the word list
    words = content_words(re.sub(r"\d", " ", shown))
    spoken_words = content_words(spoken_text)
    said_values = spoken_numbers(spoken_text)

    said = sorted(words & spoken_words)
    unsaid = sorted(words - spoken_words)
    said_numbers = 0
    for n in numbers:
        if any(same_number(n, v) for v in said_values):
            said_numbers += 1
            said.append(n.raw)
        else:
            unsaid.append(n.raw)
    total = len(words) + NUMBER_WEIGHT * len(numbers)
    coverage = (len(words & spoken_words) + NUMBER_WEIGHT * said_numbers) / total if total else 0.0
    return Score(round(coverage, 4), round((1 - coverage) * KIND_WEIGHT[kind], 4), said, unsaid)


def queue_coverage(session: Session, project_id: uuid.UUID) -> None:
    """Queue (or re-queue) scoring after the units or the transcript changed. Does not commit."""
    queue.enqueue_or_restart(
        session, project_id=project_id, kind=JOB_KIND, idempotency_key=f"{JOB_KIND}:{project_id}"
    )


def _unit_text(unit: VisualUnit) -> str:
    lines = unit.values.get("lines") or []
    return "\n".join(lines) if lines else unit.label


def score_coverage(ctx: JobContext, job: ClaimedJob) -> None:
    with ctx.session() as s:
        units = list(s.scalars(select(VisualUnit).where(VisualUnit.project_id == job.project_id)))
        audio_id = s.scalar(
            select(MediaAsset.id).where(
                MediaAsset.project_id == job.project_id,
                MediaAsset.kind == MediaKind.NORMALIZED_AUDIO,
            )
        )
        words = (
            list(
                s.execute(
                    select(TranscriptWord.start_s, TranscriptWord.text)
                    .where(TranscriptWord.media_asset_id == audio_id)
                    .order_by(TranscriptWord.idx)
                )
            )
            if audio_id
            else []
        )
        if not units or not words:
            # Nothing to compare yet: the stage that finishes later queues this job again.
            log.info("project %s: coverage waits for units and transcript", job.project_id)
            return
        pad = ctx.settings.coverage_window_pad_s
        for n, unit in enumerate(units):
            ctx.progress("compare", n / len(units))
            lo, hi = unit.t_start_s - pad, unit.t_end_s + pad
            spoken = " ".join(w.text for w in words if lo <= w.start_s <= hi)
            score = score_unit(unit.kind, _unit_text(unit), spoken)
            unit.coverage_score = score.coverage
            unit.priority = score.priority
            unit.values = {**unit.values, "said": score.said, "unsaid": score.unsaid}
        ctx.check_cancelled()
        s.commit()
    log.info("project %s: scored %d visual units", job.project_id, len(units))
    ctx.progress("compare", 1.0)
