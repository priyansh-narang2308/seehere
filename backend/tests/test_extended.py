"""Extended pause planning: paused descriptions use the silence first, stay within budget, give a
reason for every pause, and never sound over speech or another description."""

from __future__ import annotations

import random
import uuid

import pytest

from seehere.db.enums import DescriptionVariant
from seehere.schedule.cp_sat import schedule_cp_sat
from seehere.schedule.extended import plan_extended, validate_extended
from seehere.schedule.greedy import CueInput
from seehere.schedule.windows import speech_windows

S, L = DescriptionVariant.SHORT, DescriptionVariant.LONG
# Continuous speech 0-10 s with a 0.6 s gap at 4.0-4.6 (too short for standard mode).
WORDS = [(0.0, 2.0), (2.0, 4.0), (4.6, 7.0), (7.0, 10.0)]


def _cue(priority: float, earliest: float, latest: float, **durations: float) -> CueInput:
    return CueInput(
        uuid.uuid4(),
        priority,
        earliest,
        latest,
        {DescriptionVariant(k): v for k, v in durations.items()},
    )


def _plan(cues: list[CueInput], budget_pct: float = 10.0, words=WORDS, duration=10.0):
    return plan_extended(
        [],
        cues,
        words,
        duration,
        pad_s=0.15,
        budget_pct=budget_pct,
        labels={c.id: "The chart" for c in cues},
    )


def test_pause_uses_the_silence_first_and_states_why() -> None:
    cue = _cue(0.8, 1.0, 9.0, short=1.0, long=4.0)
    plan = _plan([cue])
    [p] = plan.placements
    # At 4.15 there is 0.3 s of silence (4.0 + 0.15 to 4.6 - 0.15), so the video pauses 0.7 s.
    assert (p.variant, p.start_s, p.pause_s, p.end_s) == (S, 4.15, 0.7, 5.15)
    assert p.reason == (
        "The chart is on screen while the speaker talks; the longest silence then is 0.3 s, "
        "so the video pauses 0.7 s to finish the description."
    )
    assert plan.paused_s == 0.7 and validate_extended(plan, WORDS) == []


def test_budget_is_enforced_by_priority() -> None:
    big, small = _cue(0.9, 0.0, 9.0, short=0.9), _cue(0.4, 0.0, 9.0, short=0.9)
    plan = _plan([small, big], budget_pct=10.0)  # 1.0 s budget; big uses 0.3 s of silence
    assert [p.cue_id for p in plan.pauses] == [big.id]
    assert plan.skipped == [
        (small.id, "needs a 0.9 s pause; only 0.4 s of the 1.0 s pause budget is left")
    ]


def test_standard_placements_are_kept_and_never_overlapped() -> None:
    words = [(0.0, 3.0), (6.0, 9.0)]
    windows = speech_windows(words, 9.0, pad_s=0.15, min_length_s=0.8)
    first, second = _cue(0.9, 3.0, 6.0, short=2.5), _cue(0.5, 3.0, 10.0, short=2.0)
    standard = schedule_cp_sat([first, second], windows).placed
    plan = plan_extended(
        standard, [first, second], words, 9.0, pad_s=0.15, budget_pct=50, labels={}
    )
    assert {p.cue_id: p.pause_s for p in plan.placements}[first.id] == 0.0
    assert validate_extended(plan, words) == []
    second_p = next(p for p in plan.placements if p.cue_id == second.id)
    # Right after the first: 0.2 s of silence is left before the next word, then a 1.8 s pause.
    assert (second_p.start_s, second_p.pause_s) == (5.65, 1.8)


def test_validator_flags_reasonless_or_spoken_over_pauses() -> None:
    plan = _plan([_cue(0.8, 1.0, 9.0, short=1.0)])
    bad = type(plan)([type(plan.placements[0])(uuid.uuid4(), S, 1.0, 2.0, 0.5, None)], [], 1.0, 0.5)
    problems = validate_extended(bad, WORDS)
    assert any("without a reason" in p for p in problems)
    assert any("overlaps speech" in p for p in problems)


@pytest.mark.parametrize("seed", range(60))
def test_random_lectures_stay_valid(seed: int) -> None:
    rng = random.Random(seed)
    t, words = 0.0, []
    while t < 60:
        t += rng.choice([0.0, 0.05, 0.2, 0.5, 1.5, 3.0])
        d = rng.uniform(0.1, 0.6)
        words.append((round(t, 3), round(t + d, 3)))
        t += d
    windows = speech_windows(words, 62.0, pad_s=0.15, min_length_s=0.8)
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
    standard = schedule_cp_sat(cues, windows).placed
    plan = plan_extended(
        standard, cues, words, 62.0, pad_s=0.15, budget_pct=rng.choice([0, 5, 8, 20]), labels={}
    )
    assert validate_extended(plan, words) == []
    assert len(plan.placements) + len(plan.skipped) == len(cues)
    for p in plan.placements:
        cue = next(c for c in cues if c.id == p.cue_id)
        assert cue.earliest_s - 1e-6 <= p.start_s <= cue.latest_s + 1e-6
