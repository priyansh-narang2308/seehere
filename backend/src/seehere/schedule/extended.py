"""Extended pause planning (Task 21): descriptions that found no room in standard mode may pause
the video, within a budget, and every pause states its reason.

Starting from the chosen standard schedule, the remaining cues are taken by priority (then
time, then id). For each one:
- the candidate moments are the ends of words and of other descriptions while its visual is
  relevant (anchor to the visual leaving + grace), never inside a word or description;
- at each moment the description first uses whatever silence follows, and the video pauses
  only for the rest; the moment needing the shortest pause wins (earliest on a tie);
- the shortest wording is used, because a pause costs every listener time;
- the total pause time may not exceed the budget (a share of the lecture's length).
A cue whose pause would exceed the remaining budget is skipped with that reason.

Times are source-video seconds. A placement starts at `start_s`, plays over silence until
`start_s + (end_s - start_s - pause_s)`, then the video holds that frame for `pause_s`.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass

from seehere.db.enums import DescriptionVariant
from seehere.schedule.greedy import CueInput, Placement

EPS = 1e-6
SHORTEST_FIRST = [DescriptionVariant.SHORT, DescriptionVariant.MEDIUM, DescriptionVariant.LONG]


@dataclass(frozen=True)
class ExtendedPlacement:
    cue_id: uuid.UUID
    variant: DescriptionVariant
    start_s: float
    end_s: float  # start + the wording's full length
    pause_s: float  # how long the video holds still
    reason: str | None  # why the pause was needed (required when pause_s > 0)

    @property
    def over_silence_s(self) -> float:
        return round(self.end_s - self.start_s - self.pause_s, 3)


@dataclass(frozen=True)
class ExtendedPlan:
    placements: list[ExtendedPlacement]  # standard placements (no pause) plus paused ones
    skipped: list[tuple[uuid.UUID, str]]
    budget_s: float
    paused_s: float

    @property
    def pauses(self) -> list[ExtendedPlacement]:
        return [p for p in self.placements if p.pause_s > 0]


def _ms(t: float) -> float:
    return math.ceil(round(t * 1000, 6)) / 1000


def _moments(
    words: list[tuple[float, float]], duration_s: float, pad_s: float
) -> list[tuple[float, float]]:
    """(moment, silence after it) for the start of the video and the end of every word. After
    a word the moment is `pad` later when the gap allows it, so the word is not clipped."""
    spans = sorted(words)
    starts = [s for s, _ in spans[1:]] + [duration_s + pad_s]
    out = [(0.0, round(max(0.0, (spans[0][0] - pad_s) if spans else duration_s), 3))]
    cursor = 0.0
    for (_, end), nxt in zip(spans, starts, strict=True):
        cursor = max(cursor, end)
        if nxt - cursor >= 2 * pad_s:
            at, silence = cursor + pad_s, min(nxt - pad_s, duration_s) - cursor - pad_s
        else:
            at, silence = cursor, 0.0
        at = min(at, duration_s)  # at the very end, the last frame is held
        out.append((round(at, 3), round(max(0.0, silence), 3)))
    return out


def _silence_after(
    t: float, words: list[tuple[float, float]], duration_s: float, pad_s: float
) -> float:
    if any(a < t < b for a, b in words):
        return -1.0  # inside a word: not a usable moment
    nxt = min((a - pad_s for a, _ in words if a >= t), default=duration_s)
    return round(max(0.0, min(nxt, duration_s) - t), 3)


def plan_extended(
    standard: list[Placement],
    cues: list[CueInput],
    words: list[tuple[float, float]],
    duration_s: float,
    *,
    pad_s: float,
    budget_pct: float,
    labels: dict[uuid.UUID, str],
) -> ExtendedPlan:
    budget = round(duration_s * budget_pct / 100, 3)
    taken = [(p.start_s, p.end_s) for p in standard]
    placements = [
        ExtendedPlacement(p.cue_id, p.variant, p.start_s, p.end_s, 0.0, None) for p in standard
    ]
    used, skipped = 0.0, []
    moments = _moments(words, duration_s, pad_s)
    done = {p.cue_id for p in standard}
    for cue in sorted(cues, key=lambda c: (-c.priority, c.earliest_s, str(c.id))):
        if cue.id in done:
            continue
        variant = next((v for v in SHORTEST_FIRST if v in cue.durations), None)
        if variant is None:
            continue
        need = cue.durations[variant]
        best = None
        after_others = [(b, _silence_after(b, words, duration_s, pad_s)) for _, b in taken]
        for at, silence in sorted(moments + after_others):
            if silence < 0 or at < cue.earliest_s - EPS or at > cue.latest_s + EPS:
                continue
            if any(a - EPS <= at < b - EPS for a, b in taken):
                continue  # inside another description
            nxt = min((a for a, _ in taken if a >= at - EPS), default=math.inf)
            free = max(0.0, min(silence, nxt - at, need))
            pause = _ms(need - free)
            if best is None or pause < best[0] - EPS:
                best = (pause, at, free)
        if best is None:
            skipped.append((cue.id, "no moment between words while it is on screen"))
            continue
        pause, at, free = best
        if used + pause > budget + EPS:
            skipped.append(
                (
                    cue.id,
                    f"needs a {pause:.1f} s pause; the pause budget ({budget:.1f} s) is used up",
                )
            )
            continue
        reason = None
        if pause > 0:
            label = labels.get(cue.id, "This visual")
            reason = (
                f"{label} is on screen while the speaker talks; the longest silence then is "
                f"{free:.1f} s, so the video pauses {pause:.1f} s to finish the description."
            )
        end = _ms(at + free + pause)
        placements.append(ExtendedPlacement(cue.id, variant, at, end, pause, reason))
        taken.append((at, at + free))
        used = round(used + pause, 3)
    return ExtendedPlan(sorted(placements, key=lambda p: p.start_s), skipped, budget, used)


def validate_extended(plan: ExtendedPlan, words: list[tuple[float, float]]) -> list[str]:
    """Independent check: no description is heard over speech or another description, every
    pause has a reason, and the budget holds."""
    problems = []
    parts = []
    for p in plan.placements:
        a, b = p.start_s, p.start_s + p.over_silence_s
        parts.append((a, b, p.cue_id))
        if p.end_s <= p.start_s or p.pause_s < 0:
            problems.append(f"cue {p.cue_id} has no length")
        if p.pause_s > 0 and not p.reason:
            problems.append(f"cue {p.cue_id} pauses the video without a reason")
        if b > a + EPS and any(ws < b - EPS and we > a + EPS for ws, we in words):
            problems.append(f"cue {p.cue_id} overlaps speech ({a}-{b} s)")
        if p.pause_s > 0 and any(ws + EPS < b < we - EPS for ws, we in words):
            problems.append(f"cue {p.cue_id} pauses the video inside a word")
    parts.sort()
    for (a1, b1, c1), (a2, _, c2) in zip(parts, parts[1:], strict=False):
        if a2 < b1 - EPS or (a1 == a2 and c1 != c2):
            problems.append(f"cues {c1} and {c2} overlap")
    if plan.paused_s > plan.budget_s + EPS:
        problems.append(f"pauses ({plan.paused_s} s) exceed the budget ({plan.budget_s} s)")
    return problems
