"""Speech windows (Task 18): the pauses in the lecture where a description can play without
talking over the speaker, measured from word timings.

A gap between two words (or before the first word / after the last) becomes a window after
trimming `pad` seconds from each side, so a description never clips the end of a word or the
start of the next; windows shorter than `min_length` are dropped. A lecture with no speech is
one window from start to end.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Window:
    start_s: float
    end_s: float

    @property
    def length(self) -> float:
        return self.end_s - self.start_s


def speech_windows(
    words: list[tuple[float, float]], duration_s: float, *, pad_s: float, min_length_s: float
) -> list[Window]:
    """`words` are (start, end) times in order. Leading and trailing silence get no pad on the
    video's edge, since nothing is spoken there."""
    spans = sorted(words)
    gaps: list[tuple[float, float]] = []
    cursor, first = 0.0, True
    for start, end in spans:
        gaps.append((cursor if first else cursor + pad_s, start - pad_s))
        cursor, first = max(cursor, end), False
    gaps.append((cursor + pad_s if spans else 0.0, duration_s))
    return [
        Window(round(a, 3), round(min(b, duration_s), 3))
        for a, b in gaps
        if min(b, duration_s) - a >= min_length_s
    ]


def window_for(windows: list[Window], earliest_s: float, latest_s: float) -> list[Window]:
    """The parts of the windows inside [earliest, latest]: where one cue may play."""
    out = []
    for w in windows:
        a, b = max(w.start_s, earliest_s), min(w.end_s, latest_s)
        if b > a:
            out.append(Window(a, b))  # exact: rounding could start a cue too early
    return out


_NUMBERISH = re.compile(r"\d")


def estimate_duration_s(text: str, words_per_s: float) -> float:
    """Speaking time before synthesis (measured after TTS in Task 23). A number is read as
    several words ("41.7%" is "forty one point seven percent"), so it counts as three."""
    tokens = text.split()
    weight = sum(3 if _NUMBERISH.search(t) else 1 for t in tokens)
    return round(weight / words_per_s + 0.3, 2)  # plus the voice's lead-in and tail
