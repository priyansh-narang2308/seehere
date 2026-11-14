"""Benchmark annotation format `seehere-bench/1` (see bench/README.md)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

FORMAT = "seehere-bench/1"


class AnnotationError(ValueError):
    pass


@dataclass(frozen=True)
class Visual:
    id: str
    t_start_s: float
    t_end_s: float
    text: str  # everything it shows, as written
    facts: tuple[str, ...]  # what a description must convey (quotes, numbers, names)
    must_describe: bool  # False when the speaker already conveys it


@dataclass(frozen=True)
class Annotation:
    item: str
    source_sha256: str
    duration_s: float
    speech: tuple[tuple[float, float], ...]  # reference speech intervals (seconds)
    visuals: tuple[Visual, ...]
    notes: str


def _num(v: Any, where: str) -> float:
    if isinstance(v, bool) or not isinstance(v, int | float):
        raise AnnotationError(f"{where} must be a number")
    return float(v)


def parse(data: dict[str, Any]) -> Annotation:
    if data.get("format") != FORMAT:
        raise AnnotationError(f"format must be {FORMAT!r}")
    duration = _num(data.get("duration_s"), "duration_s")
    speech = []
    for i, pair in enumerate(data.get("speech", [])):
        if not isinstance(pair, list) or len(pair) != 2:
            raise AnnotationError(f"speech[{i}] must be [start_s, end_s]")
        a, b = _num(pair[0], f"speech[{i}]"), _num(pair[1], f"speech[{i}]")
        if not 0 <= a < b <= duration + 1e-6:
            raise AnnotationError(f"speech[{i}] is outside the video or empty")
        speech.append((a, b))
    visuals = []
    seen = set()
    for i, v in enumerate(data.get("visuals", [])):
        vid = str(v.get("id", ""))
        if not vid or vid in seen:
            raise AnnotationError(f"visuals[{i}] needs a unique id")
        seen.add(vid)
        a = _num(v.get("t_start_s"), f"{vid}.t_start_s")
        b = _num(v.get("t_end_s"), f"{vid}.t_end_s")
        if not 0 <= a < b <= duration + 1e-6:
            raise AnnotationError(f"{vid} is outside the video or empty")
        facts = v.get("facts", [])
        if not isinstance(facts, list) or not all(isinstance(f, str) and f for f in facts):
            raise AnnotationError(f"{vid}.facts must be a list of strings")
        visuals.append(
            Visual(vid, a, b, str(v.get("text", "")), tuple(facts), bool(v.get("must_describe")))
        )
    return Annotation(
        item=str(data.get("item") or ""),
        source_sha256=str(data.get("source_sha256") or ""),
        duration_s=duration,
        speech=tuple(sorted(speech)),
        visuals=tuple(visuals),
        notes=str(data.get("notes", "")),
    )


def load(path: Path) -> Annotation:
    try:
        return parse(json.loads(path.read_text("utf-8")))
    except json.JSONDecodeError as exc:
        raise AnnotationError(f"{path}: not valid JSON ({exc})") from exc
