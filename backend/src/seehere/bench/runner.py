"""Score every system on one annotated item and write the results (JSON and Markdown)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from seehere.bench.annotation import Annotation
from seehere.bench.metrics import score
from seehere.bench.systems import (
    UNAVAILABLE,
    BenchError,
    SystemRun,
    microsoft_system,
    seehere_systems,
    source_sha256,
)
from seehere.core.config import Settings


def run_item(
    s: Session, cfg: Settings, ann: Annotation, pid: uuid.UUID, microsoft_vtt: Path | None
) -> dict[str, Any]:
    sha = source_sha256(s, pid)
    if sha is None:
        raise BenchError("the project has no source video")
    if ann.source_sha256 and sha != ann.source_sha256:
        raise BenchError("the project's video is not the annotated one (sha256 differs)")
    systems = [microsoft_system(microsoft_vtt), *seehere_systems(s, cfg, pid)]
    return results(ann, systems)


def results(ann: Annotation, systems: list[SystemRun]) -> dict[str, Any]:
    return {
        "item": ann.item,
        "source_sha256": ann.source_sha256,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "systems": [
            {
                "system": r.system,
                "evidence": r.label,
                "note": r.note,
                "metrics": None if r.label == UNAVAILABLE else score(ann, r.said),
                "descriptions": [
                    {"start_s": d.start_s, "end_s": d.end_s, "pause_s": d.pause_s, "text": d.text}
                    for d in r.said
                ],
            }
            for r in systems
        ],
    }


def _pct(v: float | None) -> str:
    return "n/a" if v is None else f"{v * 100:.0f}%"


def markdown(res: dict[str, Any]) -> str:
    rows = [
        "| System | Evidence | Descriptions | Visual recall | Fact recall | Over speech (s) "
        "| Paused (s) | Unsupported numbers | Note |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in res["systems"]:
        m = r["metrics"]
        if m is None:
            dashes = " | ".join(["–"] * 6)
            rows.append(f"| {r['system']} | {r['evidence']} | {dashes} | {r['note']} |")
            continue
        rows.append(
            f"| {r['system']} | {r['evidence']} | {m['descriptions']} | {_pct(m['visual_recall'])} "
            f"| {_pct(m['fact_recall'])} | {m['speech_overlap_s']:.2f} | {m['paused_s']:.2f} "
            f"| {', '.join(m['unsupported_numbers']) or 'none'} | {r['note']} |"
        )
    return (
        f"# Benchmark: {res['item']}\n\n"
        f"Generated {res['generated_at']} by `python -m seehere.bench`. Evidence labels: "
        "OBSERVED = the system ran on this item; SIMULATED = computed under the stated "
        "assumption; UNAVAILABLE = not run (no numbers reported).\n\n"
        + "\n".join(rows)
        + "\n\nMetric definitions: see `bench/README.md`. Unsupported numbers are a proxy for "
        "invented values, not a complete hallucination measure. One short synthetic item is a "
        "smoke test, not evidence of general quality.\n"
    )


def write(res: dict[str, Any], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    j, m = out_dir / f"{res['item']}.json", out_dir / f"{res['item']}.md"
    j.write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n", "utf-8")
    m.write_text(markdown(res), "utf-8")
    return j, m
