"""Speech windows and the greedy scheduler: rules, determinism, and an independent validator
that confirms zero overlap with speech or between cues on many random lectures."""

from __future__ import annotations

import random
import uuid

import pytest

from seehere.db.enums import DescriptionVariant
from seehere.schedule.greedy import CueInput, Placement, schedule_greedy, validate
from seehere.schedule.windows import Window, estimate_duration_s, speech_windows

S, M, L = DescriptionVariant.SHORT, DescriptionVariant.MEDIUM, DescriptionVariant.LONG


def _windows(words: list[tuple[float, float]], duration: float) -> list[Window]:
    return speech_windows(words, duration, pad_s=0.15, min_length_s=0.8)


def test_windows_are_padded_pauses_between_words() -> None:
    words = [(1.0, 1.4), (1.5, 2.0), (4.0, 4.5), (4.9, 5.3)]
    assert _windows(words, 8.0) == [
        Window(0.0, 0.85),  # before the first word: no pad at the start of the video
        Window(2.15, 3.85),  # a 2 s pause loses 0.15 s on each side
        Window(5.45, 8.0),  # after the last word
    ]  # the 0.1 s and 0.4 s gaps are too short to hold anything
    assert _windows([], 6.0) == [Window(0.0, 6.0)]  # a silent lecture is one long pause


def test_overlapping_word_timings_never_open_a_window() -> None:
    assert _windows([(1.0, 3.0), (2.0, 2.5), (4.5, 5.0)], 6.0) == [
        Window(0.0, 0.85),
        Window(3.15, 4.35),
        Window(5.15, 6.0),
    ]


def test_duration_estimate_counts_numbers_as_several_words() -> None:
    assert estimate_duration_s("On screen: Next steps.", 2.6) == pytest.approx(
        4 / 2.6 + 0.3, abs=0.01
    )
    assert estimate_duration_s("Margin 41.7%", 2.6) > estimate_duration_s("Margin high", 2.6)


def _cue(priority: float, earliest: float, latest: float, **durations: float) -> CueInput:
    variants = {DescriptionVariant(k): v for k, v in durations.items()}
    return CueInput(uuid.uuid4(), priority, earliest, latest, variants)


def test_priority_claims_a_contested_pause_and_the_longest_wording_that_fits() -> None:
    windows = [Window(2.0, 5.0)]
    low = _cue(0.3, 0.0, 6.0, short=2.0)
    high = _cue(0.9, 1.0, 6.0, short=1.0, medium=2.5, long=4.0)
    placed, skipped = schedule_greedy([low, high], windows)
    assert placed == [Placement(high.id, M, 2.0, 4.5)]  # long (4 s) does not fit in 3 s
    assert [(k.cue_id, k.reason) for k in skipped] == [
        (low.id, "the longest free pause (3.0 s) is too short")
    ]


def test_a_cue_plays_only_while_its_visual_is_relevant() -> None:
    windows = [Window(0.0, 2.0), Window(10.0, 20.0)]
    late = _cue(0.5, 3.0, 9.0, short=1.0)  # on screen 3-9 s: no pause then
    placed, skipped = schedule_greedy([late], windows)
    assert placed == [] and skipped[0].reason == "no pause in speech while it is on screen"
    anchored = _cue(0.5, 11.0, 15.0, short=1.0)
    assert schedule_greedy([anchored], windows)[0] == [Placement(anchored.id, S, 11.0, 12.0)]


def test_cues_share_a_long_pause_without_overlapping() -> None:
    windows = [Window(0.0, 6.0)]
    cues = [_cue(0.5, 0.0, 6.0, short=2.0) for _ in range(4)]
    placed, skipped = schedule_greedy(cues, windows)
    assert [(p.start_s, p.end_s) for p in placed] == [(0.0, 2.0), (2.0, 4.0), (4.0, 6.0)]
    assert len(skipped) == 1 and validate(placed, windows) == []


def test_validator_catches_speech_and_cue_overlap() -> None:
    windows = [Window(0.0, 2.0), Window(4.0, 8.0)]
    a, b = uuid.uuid4(), uuid.uuid4()
    assert validate([Placement(a, S, 1.5, 2.5)], windows) == [
        f"cue {a} overlaps speech (1.5-2.5 s)"
    ]
    assert validate([Placement(a, S, 4.0, 6.0), Placement(b, S, 5.0, 7.0)], windows) == [
        f"cues {a} and {b} overlap"
    ]


@pytest.mark.parametrize("seed", range(200))
def test_random_lectures_schedule_deterministically_with_zero_overlap(seed: int) -> None:
    rng = random.Random(seed)
    t, words = 0.0, []
    while t < 60:
        t += rng.choice([0.05, 0.1, 0.2, 0.5, 1.2, 2.5, 4.0])
        d = rng.uniform(0.1, 0.6)
        words.append((round(t, 3), round(t + d, 3)))
        t += d
    windows = _windows(words, 62.0)
    cues = []
    for _ in range(rng.randint(1, 15)):
        start = rng.uniform(0, 55)
        lengths = sorted(rng.uniform(0.5, 6) for _ in range(3))
        cues.append(
            _cue(
                rng.random(),
                start,
                start + rng.uniform(2, 12),
                short=lengths[0],
                medium=lengths[1],
                long=lengths[2],
            )
        )
    placed, skipped = schedule_greedy(cues, windows)
    assert validate(placed, windows) == []
    assert len(placed) + len(skipped) == len(cues)
    for p in placed:
        cue = next(c for c in cues if c.id == p.cue_id)
        assert cue.earliest_s <= p.start_s and p.end_s <= cue.latest_s + 1e-6
    shuffled = cues[:]
    rng.shuffle(shuffled)
    assert schedule_greedy(shuffled, windows) == (placed, skipped)  # order-independent
