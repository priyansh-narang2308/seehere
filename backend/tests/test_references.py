"""Visual reference resolution: phrase detection, linking with confidence, and ambiguity flagged
instead of guessed."""

from __future__ import annotations

import uuid

import pytest

from seehere.db.enums import ReferenceStatus, VisualKind
from seehere.references.resolve import Candidate, Word, detect_phrases, resolve

THRESHOLD = 0.5


def _words(text: str) -> list[Word]:
    return [Word(uuid.uuid4(), 0.4 * i, w) for i, w in enumerate(text.split())]


def _phrases(text: str) -> list[str]:
    words = _words(text)
    return [p.text(words) for p in detect_phrases(words)]


@pytest.mark.parametrize(
    "speech,found",
    [
        ("so this blue line here goes up", ["this blue line here"]),
        ("and these two bars are taller", ["these two bars"]),
        ("look at that one here please", ["that one here"]),
        ("the answer is right here.", ["right here"]),
        ("as you can see, it falls", ["as you can see"]),
        ("this table, and this equation", ["this table", "this equation"]),
        # not pointers: no visual noun, a vague noun alone, or "point" meaning a moment
        ("that is important and that one matters", []),
        ("at this point we stop", []),
        ("this part of the argument", []),
        ("there were many students", []),
    ],
)
def test_detects_spoken_pointers(speech: str, found: list[str]) -> None:
    assert _phrases(speech) == found


def _unit(kind: VisualKind, text: str, box: tuple[float, float, float, float]) -> Candidate:
    return Candidate(uuid.uuid4(), kind, text, 0.0, 10.0, box)


TITLE = _unit(VisualKind.TEXT_BLOCK, "Quarterly Revenue", (0.06, 0.08, 0.4, 0.1))
REVENUE = _unit(VisualKind.TEXT_BLOCK, "Revenue rose 12.5% to $3.2M", (0.06, 0.33, 0.5, 0.06))
MARGIN = _unit(VisualKind.TEXT_BLOCK, "Operating margin 41.7% in 2022", (0.06, 0.46, 0.5, 0.06))
SLIDE = [TITLE, REVENUE, MARGIN]


def test_spoken_number_after_the_pointer_links_the_unit() -> None:
    r = resolve("this number here", "twelve point five percent", "number", SLIDE, THRESHOLD)
    assert (r.unit_id, r.status) == (REVENUE.id, ReferenceStatus.LINKED)
    assert r.confidence >= 0.8


def test_shared_words_link_the_unit() -> None:
    r = resolve("this figure", "the operating margin", "figure", SLIDE, THRESHOLD)
    assert (r.unit_id, r.status) == (MARGIN.id, ReferenceStatus.LINKED)


def test_ambiguous_pointer_is_flagged_not_guessed() -> None:
    r = resolve("this line here", "is important", "line", SLIDE, THRESHOLD)
    assert (r.unit_id, r.status, r.confidence) == (None, ReferenceStatus.AMBIGUOUS, 0.0)
    # Both candidates mention revenue equally: still not a guess.
    tie = resolve("this revenue figure", "", "figure", [TITLE, REVENUE], THRESHOLD)
    assert tie.status is ReferenceStatus.AMBIGUOUS and tie.unit_id is None


def test_kind_and_place_disambiguate() -> None:
    left = _unit(VisualKind.CHART, "Sales", (0.05, 0.2, 0.4, 0.6))
    right = _unit(VisualKind.CHART, "Costs", (0.55, 0.2, 0.4, 0.6))
    table = _unit(VisualKind.TABLE, "Totals", (0.2, 0.85, 0.6, 0.1))
    r = resolve("this table", "", "table", [left, right, table], THRESHOLD)
    assert (r.unit_id, r.status) == (table.id, ReferenceStatus.LINKED)
    r = resolve("this chart", "on the right shows", "chart", [left, right, table], THRESHOLD)
    assert (r.unit_id, r.status) == (right.id, ReferenceStatus.LINKED)
    r = resolve("this chart", "goes up", "chart", [left, right], THRESHOLD)
    assert r.status is ReferenceStatus.AMBIGUOUS  # two charts, nothing to tell them apart


def test_lone_unit_links_and_nothing_on_screen_is_unresolved() -> None:
    r = resolve("right here", "", None, [TITLE], THRESHOLD)
    assert (r.unit_id, r.status, r.confidence) == (TITLE.id, ReferenceStatus.LINKED, 0.5)
    r = resolve("this chart", "", "chart", [], THRESHOLD)
    assert (r.unit_id, r.status) == (None, ReferenceStatus.UNRESOLVED)
