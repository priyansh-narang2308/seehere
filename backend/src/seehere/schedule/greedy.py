"""Greedy scheduler (Task 19), standard mode: descriptions play only inside speech windows,
never over the speaker and never over each other.

Rules, applied in a fixed order so the same input always gives the same schedule:
1. Cues are taken by priority (highest first), then anchor time, then id.
2. A cue may play from its anchor (when its visual appears, or is pointed at) until `grace`
   seconds after the visual leaves the screen.
3. For each cue, the longest wording that fits is chosen (long, then medium, then short), at
   the earliest free moment inside a window within that range.
4. A cue that fits nowhere is skipped, with the reason recorded.
`validate` re-checks any schedule independently: no overlap with speech or another cue.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass

from seehere.db.enums import DescriptionVariant
from seehere.schedule.windows import Window, window_for

VARIANT_ORDER = [DescriptionVariant.LONG, DescriptionVariant.MEDIUM, DescriptionVariant.SHORT]
EPS = 1e-6


@dataclass(frozen=True)
class CueInput:
    id: uuid.UUID
    priority: float
    earliest_s: float  # anchor
    latest_s: float  # visual leaves the screen + grace
    durations: dict[DescriptionVariant, float]  # estimated speaking time per wording


@dataclass(frozen=True)
class Placement:
    cue_id: uuid.UUID
    variant: DescriptionVariant
    start_s: float
    end_s: float


@dataclass(frozen=True)
class Skipped:
    cue_id: uuid.UUID
    reason: str


def _up(t: float) -> float:
    """Round up to the millisecond, so rounding never moves a cue earlier than allowed."""
    return math.ceil(round(t * 1000, 6)) / 1000


def _free(window: Window, taken: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Unoccupied parts of a window."""
    out, cursor = [], window.start_s
    for a, b in sorted(taken):
        if b <= cursor or a >= window.end_s:
            continue
        if a > cursor:
            out.append((cursor, a))
        cursor = max(cursor, b)
    if cursor < window.end_s:
        out.append((cursor, window.end_s))
    return out


def schedule_greedy(
    cues: list[CueInput], windows: list[Window]
) -> tuple[list[Placement], list[Skipped]]:
    placed: list[Placement] = []
    skipped: list[Skipped] = []
    for cue in sorted(cues, key=lambda c: (-c.priority, c.earliest_s, str(c.id))):
        allowed = window_for(windows, cue.earliest_s, cue.latest_s)
        taken = [(p.start_s, p.end_s) for p in placed]
        choice = None
        for variant in VARIANT_ORDER:
            need = cue.durations.get(variant)
            if need is None:
                continue
            for w in allowed:
                for a, b in _free(w, taken):
                    start = _up(a)
                    end = _up(start + need)
                    if end <= b + EPS:
                        choice = Placement(cue.id, variant, start, end)
                        break
                if choice:
                    break
            if choice:
                break
        if choice:
            placed.append(choice)
        elif not allowed:
            skipped.append(Skipped(cue.id, "no pause in speech while it is on screen"))
        else:
            longest = max(w.length for w in allowed)
            skipped.append(
                Skipped(cue.id, f"the longest free pause ({longest:.1f} s) is too short")
            )
    return sorted(placed, key=lambda p: p.start_s), skipped


def validate(placements: list[Placement], windows: list[Window]) -> list[str]:
    """Independent check of a standard-mode schedule. Returns the violations (none = valid)."""
    problems = []
    for p in placements:
        if p.end_s <= p.start_s:
            problems.append(f"cue {p.cue_id} has no length")
        if not any(w.start_s - EPS <= p.start_s and p.end_s <= w.end_s + EPS for w in windows):
            problems.append(f"cue {p.cue_id} overlaps speech ({p.start_s}-{p.end_s} s)")
    ordered = sorted(placements, key=lambda p: p.start_s)
    for a, b in zip(ordered, ordered[1:], strict=False):
        if b.start_s < a.end_s - EPS:
            problems.append(f"cues {a.cue_id} and {b.cue_id} overlap")
    return problems
