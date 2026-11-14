"""CP-SAT scheduler: same rules and validator as greedy, never worse than greedy on priority,
deterministic, and every skipped cue explained."""

from __future__ import annotations

import random
import uuid

import pytest

from seehere.db.enums import DescriptionVariant
from seehere.schedule.cp_sat import schedule_cp_sat
from seehere.schedule.greedy import CueInput, Placement, schedule_greedy, validate
from seehere.schedule.windows import Window, speech_windows

S, M, L = DescriptionVariant.SHORT, DescriptionVariant.MEDIUM, DescriptionVariant.LONG


def _cue(priority: float, earliest: float, latest: float, **durations: float) -> CueInput:
    variants = {DescriptionVariant(k): v for k, v in durations.items()}
    return CueInput(uuid.uuid4(), priority, earliest, latest, variants)


def test_joint_solving_beats_one_at_a_time() -> None:
    # Greedy gives the 3 s pause to the top cue's long wording first; nothing is left for the
    # second. CP-SAT sees both, uses the short wording, and places both.
    windows = [Window(0.0, 3.0)]
    top = _cue(0.9, 0.0, 3.0, short=1.5, long=3.0)
    second = _cue(0.8, 0.0, 3.0, short=1.5)
    greedy, _ = schedule_greedy([top, second], windows)
    assert [p.cue_id for p in greedy] == [top.id]
    result = schedule_cp_sat([top, second], windows)
    assert result.status == "optimal" and result.skipped == []
    assert result.placed == [Placement(top.id, S, 0.0, 1.5), Placement(second.id, S, 1.5, 3.0)]


def test_longest_wording_and_earliest_start_when_there_is_room() -> None:
    cue = _cue(0.5, 1.0, 9.0, short=1.0, medium=2.0, long=3.0)
    result = schedule_cp_sat([cue], [Window(0.0, 10.0)])
    assert result.placed == [Placement(cue.id, L, 1.0, 4.0)]


def test_skipped_cues_are_explained() -> None:
    windows = [Window(0.0, 2.0), Window(10.0, 12.0)]
    unseen = _cue(0.5, 3.0, 9.0, short=1.0)
    long_only = _cue(0.5, 0.0, 2.0, short=2.5)
    a, b = (_cue(p, 10.0, 12.0, short=1.5) for p in (0.9, 0.4))
    reasons = {
        k.cue_id: k.reason for k in schedule_cp_sat([unseen, long_only, a, b], windows).skipped
    }
    assert reasons == {
        unseen.id: "no pause in speech while it is on screen",
        long_only.id: "the longest free pause (2.0 s) is too short",
        b.id: "its pause went to higher-priority descriptions",
    }


def test_nothing_to_schedule() -> None:
    result = schedule_cp_sat([], [])
    assert (result.placed, result.skipped, result.status) == ([], [], "optimal")


@pytest.mark.parametrize("seed", range(60))
def test_random_lectures_valid_deterministic_and_never_worse_than_greedy(seed: int) -> None:
    rng = random.Random(seed)
    t, words = 0.0, []
    while t < 60:
        t += rng.choice([0.05, 0.1, 0.2, 0.5, 1.2, 2.5, 4.0])
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
    result = schedule_cp_sat(cues, windows)
    assert result.status == "optimal"
    assert validate(result.placed, windows) == []
    assert len(result.placed) + len(result.skipped) == len(cues)
    for p in result.placed:
        cue = next(c for c in cues if c.id == p.cue_id)
        assert cue.earliest_s <= p.start_s and p.end_s <= cue.latest_s + 1e-6
    prio = {c.id: c.priority for c in cues}
    greedy, _ = schedule_greedy(cues, windows)
    assert sum(prio[p.cue_id] for p in result.placed) >= sum(prio[p.cue_id] for p in greedy) - 1e-3
    shuffled = cues[:]
    rng.shuffle(shuffled)
    assert schedule_cp_sat(shuffled, windows).placed == result.placed
