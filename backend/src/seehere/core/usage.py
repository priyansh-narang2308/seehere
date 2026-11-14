"""Per-job measurement: wall time, CPU, memory and every hosted-provider call (Task 33).

The worker opens a `measure()` block around each job. Providers call `record_call()` after each
HTTP request; outside a measured block (tests, scripts) the call is simply not collected. Only
counts, sizes, HTTP codes and timings are kept, never the text, audio or images that were sent.

Memory figures come from `getrusage`, which reports the process's high-water mark so far, so a
job's `peak_rss_mb` is the worker's peak at the end of that job, not the job's own peak.
"""

from __future__ import annotations

import resource
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from typing import Any

# ru_maxrss is bytes on macOS and kibibytes on Linux.
_RSS_TO_MB = 1 / (1024 * 1024) if sys.platform == "darwin" else 1 / 1024


@dataclass(frozen=True)
class ProviderCall:
    service: str  # "vultr"
    operation: str  # "vision" | "tts" | "stt"
    status: int | None  # HTTP status, None if no response arrived
    duration_ms: int
    units: dict[str, float] = field(default_factory=dict)  # e.g. {"input_chars": 42}


@dataclass
class Measurement:
    run_s: float = 0.0
    cpu_s: float = 0.0
    child_cpu_s: float = 0.0  # ffmpeg, Piper, Tesseract and other subprocesses
    peak_rss_mb: float = 0.0
    child_peak_rss_mb: float = 0.0
    provider_calls: list[ProviderCall] = field(default_factory=list)

    def as_json(self) -> dict[str, Any]:
        data = asdict(self)
        for key in ("run_s", "cpu_s", "child_cpu_s", "peak_rss_mb", "child_peak_rss_mb"):
            data[key] = round(data[key], 3)
        return data


_current: ContextVar[Measurement | None] = ContextVar("seehere_measurement", default=None)


def _cpu(who: int) -> tuple[float, float]:
    r = resource.getrusage(who)
    return r.ru_utime + r.ru_stime, r.ru_maxrss * _RSS_TO_MB


@contextmanager
def measure() -> Iterator[Measurement]:
    """Measure the enclosed work. The result is filled in when the block exits, even on error."""
    m = Measurement()
    token = _current.set(m)
    start = time.monotonic()
    cpu0, _ = _cpu(resource.RUSAGE_SELF)
    child0, _ = _cpu(resource.RUSAGE_CHILDREN)
    try:
        yield m
    finally:
        _current.reset(token)
        cpu1, rss = _cpu(resource.RUSAGE_SELF)
        child1, child_rss = _cpu(resource.RUSAGE_CHILDREN)
        m.run_s = time.monotonic() - start
        m.cpu_s = cpu1 - cpu0
        m.child_cpu_s = child1 - child0
        m.peak_rss_mb = rss
        m.child_peak_rss_mb = child_rss


def record_call(
    operation: str,
    status: int | None,
    started: float,
    units: dict[str, float] | None = None,
    *,
    service: str = "vultr",
) -> None:
    """Record one provider request. `started` is a `time.monotonic()` reading."""
    m = _current.get()
    if m is None:
        return
    duration_ms = round((time.monotonic() - started) * 1000)
    call = ProviderCall(service, operation, status, duration_ms, dict(units or {}))
    m.provider_calls.append(call)
