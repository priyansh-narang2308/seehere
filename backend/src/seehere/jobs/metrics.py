"""Stage timings, resource use and hosted-provider spend, read from job measurements (Task 33).

Every job attempt stores what the worker measured (see `seehere.core.usage`). This module turns
those rows into a per-project breakdown and a summary across all projects still kept. Costs are
estimated only from unit prices the operator configured; with none set, spend is reported as
calls and units without a dollar figure.
"""

from __future__ import annotations

import math
import uuid
from collections import defaultdict
from collections.abc import Iterable, Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from seehere.core.config import Settings
from seehere.db.enums import MediaKind
from seehere.db.models import Job, MediaAsset

OPERATIONS = ("vision", "tts", "stt")


def _percentile(values: Sequence[float], q: float) -> float:
    """Nearest-rank percentile (q in 0..100) of a non-empty list."""
    ordered = sorted(values)
    rank = max(1, math.ceil(q / 100 * len(ordered)))
    return ordered[rank - 1]


def _cost(settings: Settings, operation: str, units: dict[str, float]) -> float | None:
    if operation == "vision" and settings.vultr_price_per_million_tokens_usd is not None:
        tokens = units.get("prompt_tokens", 0) + units.get("completion_tokens", 0)
        return tokens / 1e6 * settings.vultr_price_per_million_tokens_usd
    if operation == "tts" and settings.vultr_price_per_million_tts_chars_usd is not None:
        return units.get("input_chars", 0) / 1e6 * settings.vultr_price_per_million_tts_chars_usd
    if operation == "stt" and settings.vultr_price_per_stt_minute_usd is not None:
        return units.get("audio_s", 0) / 60 * settings.vultr_price_per_stt_minute_usd
    return None


def provider_spend(settings: Settings, attempts: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Calls, failures, units, latency and estimated cost per provider operation."""
    calls: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for attempt in attempts:
        for call in attempt.get("provider_calls", []):
            calls[call["operation"]].append(call)
    rows = []
    for op in sorted(calls, key=lambda o: (OPERATIONS + (o,)).index(o)):
        units: dict[str, float] = defaultdict(float)
        for call in calls[op]:
            for name, value in call.get("units", {}).items():
                units[name] += value
        # Only successful calls are billed; failed ones are counted but cost nothing.
        billed: dict[str, float] = defaultdict(float)
        for call in calls[op]:
            if call.get("status") == 200:
                for name, value in call.get("units", {}).items():
                    billed[name] += value
        cost = _cost(settings, op, billed)
        rows.append(
            {
                "operation": op,
                "calls": len(calls[op]),
                "failed": sum(1 for c in calls[op] if c.get("status") != 200),
                "units": {k: round(v, 3) for k, v in sorted(units.items())},
                "mean_latency_ms": round(sum(c["duration_ms"] for c in calls[op]) / len(calls[op])),
                "estimated_cost_usd": None if cost is None else round(cost, 6),
            }
        )
    return rows


def _attempt_totals(attempts: Sequence[dict[str, Any]]) -> dict[str, float]:
    return {
        key: round(sum(a.get(key, 0.0) for a in attempts), 3)
        for key in ("run_s", "cpu_s", "child_cpu_s")
    }


def project_metrics(session: Session, settings: Settings, project_id: uuid.UUID) -> dict[str, Any]:
    jobs = session.scalars(
        select(Job).where(Job.project_id == project_id).order_by(Job.created_at, Job.id)
    ).all()
    video_s = session.scalar(
        select(MediaAsset.duration_s).where(
            MediaAsset.project_id == project_id, MediaAsset.kind == MediaKind.SOURCE_VIDEO
        )
    )
    stages: list[dict[str, Any]] = []
    for job in jobs:
        attempts = list(job.metrics or [])
        stages.append(
            {
                "job_id": str(job.id),
                "kind": job.kind,
                "status": job.status.value,
                "attempts": job.attempts,
                **_attempt_totals(attempts),
                "peak_rss_mb": max((a.get("peak_rss_mb", 0.0) for a in attempts), default=None),
                "provider_calls": sum(len(a.get("provider_calls", [])) for a in attempts),
            }
        )
    all_attempts = [a for job in jobs for a in (job.metrics or [])]
    processing_s = round(sum(float(st["run_s"]) for st in stages), 3)
    measured = [j for j in jobs if j.metrics]
    elapsed_s = None
    if measured and all(j.finished_at is not None for j in measured):
        start = min(j.created_at for j in measured)
        end = max(j.finished_at for j in measured if j.finished_at)
        elapsed_s = round((end - start).total_seconds(), 3)
    return {
        "video_duration_s": video_s,
        "processing_s": processing_s,
        "elapsed_s": elapsed_s,
        # Seconds of processing per second of lecture: below 1 is faster than real time.
        "processing_per_video_s": round(processing_s / video_s, 3) if video_s else None,
        "stages": stages,
        "providers": provider_spend(settings, all_attempts),
        "prices_configured": _prices_configured(settings),
    }


def summary(session: Session, settings: Settings) -> dict[str, Any]:
    """Run-time distribution per job kind over every measured attempt still in the database."""
    rows = session.execute(select(Job.kind, Job.metrics).where(Job.metrics != [])).all()
    by_kind: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for kind, metrics in rows:
        by_kind[kind].extend(metrics)
    stages = []
    for kind in sorted(by_kind):
        attempts = by_kind[kind]
        runs = [a.get("run_s", 0.0) for a in attempts]
        stages.append(
            {
                "kind": kind,
                "attempts": len(attempts),
                "failed": sum(1 for a in attempts if a.get("outcome") != "succeeded"),
                "p50_run_s": round(_percentile(runs, 50), 3),
                "p95_run_s": round(_percentile(runs, 95), 3),
                "max_run_s": round(max(runs), 3),
                "mean_cpu_s": round(
                    sum(a.get("cpu_s", 0.0) + a.get("child_cpu_s", 0.0) for a in attempts)
                    / len(attempts),
                    3,
                ),
                "max_peak_rss_mb": round(max(a.get("peak_rss_mb", 0.0) for a in attempts), 1),
            }
        )
    every = [a for attempts in by_kind.values() for a in attempts]
    return {
        "stages": stages,
        "providers": provider_spend(settings, every),
        "prices_configured": _prices_configured(settings),
    }


def _prices_configured(settings: Settings) -> bool:
    return any(
        p is not None
        for p in (
            settings.vultr_price_per_million_tokens_usd,
            settings.vultr_price_per_million_tts_chars_usd,
            settings.vultr_price_per_stt_minute_usd,
        )
    )
