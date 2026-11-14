"""Metrics for one system's descriptions against one annotation. Pure functions.

- `speech_overlap_s`: seconds of description heard over reference speech (lower is better;
  extended-mode pauses are not heard over speech, so only the part played over audio counts);
- `visual_recall`: share of must-describe visuals with a description, started while the visual
  is on screen (or within `grace_s` after), that conveys at least one of its facts;
- `fact_recall`: share of must-describe facts conveyed by such a description;
- `unsupported_numbers`: numbers spoken in descriptions that appear nowhere on screen in the
  annotation. A proxy for invented values, not a full hallucination measure;
- `described_s`, `paused_s`, `descriptions`: how much was said and how long the video paused.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from seehere.bench.annotation import Annotation
from seehere.text.numbers import extract_numbers

GRACE_S = 2.0


@dataclass(frozen=True)
class Said:
    start_s: float
    end_s: float  # start + spoken length + pause
    text: str
    pause_s: float = 0.0

    @property
    def heard_end_s(self) -> float:
        return self.end_s - self.pause_s


def norm(text: str) -> str:
    """Lower case, punctuation removed (decimal points, % and $ kept), spaces collapsed."""
    t = text.casefold().replace("’", "'")
    t = re.sub(r"[^\w%$.'\s]", " ", t)
    t = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", t)  # keep decimal points only
    return re.sub(r"\s+", " ", t).strip()


def conveys(text: str, fact: str) -> bool:
    f = norm(fact)
    return bool(f) and f" {f} " in f" {norm(text)} "


def _overlap(a: float, b: float, spans: tuple[tuple[float, float], ...]) -> float:
    return sum(max(0.0, min(b, e) - max(a, s)) for s, e in spans)


def _numbers(text: str) -> set[tuple[str, str]]:
    return {(str(n.value.normalize()), str(n.scale)) for n in extract_numbers(text)}


def score(ann: Annotation, said: list[Said], *, grace_s: float = GRACE_S) -> dict[str, Any]:
    must = [v for v in ann.visuals if v.must_describe]
    facts_total = sum(len(v.facts) for v in must)
    facts_hit = visuals_hit = 0
    per_visual = []
    for v in must:
        near = [d for d in said if v.t_start_s - 1e-6 <= d.start_s <= v.t_end_s + grace_s]
        hit = [f for f in v.facts if any(conveys(d.text, f) for d in near)]
        facts_hit += len(hit)
        visuals_hit += bool(hit)
        per_visual.append({"id": v.id, "facts": len(v.facts), "conveyed": hit})
    shown: set[tuple[str, str]] = set()
    for v in ann.visuals:
        shown |= _numbers(v.text)
    unsupported = sorted(
        {n.raw for d in said for n in extract_numbers(d.text) if not _numbers(n.raw) <= shown}
    )
    return {
        "descriptions": len(said),
        "described_s": round(sum(d.heard_end_s - d.start_s for d in said), 3),
        "paused_s": round(sum(d.pause_s for d in said), 3),
        "speech_overlap_s": round(
            sum(_overlap(d.start_s, d.heard_end_s, ann.speech) for d in said), 3
        ),
        "visual_recall": round(visuals_hit / len(must), 4) if must else None,
        "fact_recall": round(facts_hit / facts_total, 4) if facts_total else None,
        "unsupported_numbers": unsupported,
        "per_visual": per_visual,
    }
