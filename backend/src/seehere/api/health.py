"""Health checks. They report real, observed state and never call paid AI endpoints."""

from __future__ import annotations

import shutil
import subprocess  # nosec B404 - fixed argv lists, no shell
import time
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from seehere.core.config import Settings

Status = Literal["ok", "degraded", "down"]


class ComponentHealth(BaseModel):
    status: Status
    detail: str
    latency_ms: float | None = None


class HealthReport(BaseModel):
    status: Status
    version: str
    environment: str
    components: dict[str, ComponentHealth]


def check_database(settings: Settings) -> ComponentHealth:
    started = time.perf_counter()
    try:
        engine = create_engine(
            settings.database_url, pool_pre_ping=True, connect_args={"connect_timeout": 2}
        )
        with engine.connect() as conn:
            version = conn.execute(text("select current_setting('server_version')")).scalar_one()
        engine.dispose()
    except SQLAlchemyError as exc:
        # Do not echo the URL (it may contain credentials); only the exception class.
        return ComponentHealth(status="down", detail=f"unreachable ({type(exc).__name__})")
    return ComponentHealth(
        status="ok",
        detail=f"postgres {version}",
        latency_ms=round((time.perf_counter() - started) * 1000, 1),
    )


def check_binary(binary: str, version_args: list[str]) -> ComponentHealth:
    path = shutil.which(binary)
    if path is None:
        return ComponentHealth(status="down", detail=f"{binary} not found on PATH")
    try:
        out = subprocess.run(  # noqa: S603 - argv list built from config + constants
            [path, *version_args], capture_output=True, text=True, timeout=5, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return ComponentHealth(
            status="down", detail=f"{binary} failed to run ({type(exc).__name__})"
        )
    first_line = (out.stdout or out.stderr).strip().splitlines()[:1]
    return ComponentHealth(status="ok", detail=first_line[0] if first_line else binary)


def check_providers(settings: Settings) -> ComponentHealth:
    """Configuration presence only. Real capability tests live in provider integration tests."""
    configured = []
    if settings.vultr_inference_api_key:
        configured.append("vultr-inference")
    if settings.gemini_api_key:
        configured.append("gemini")
    if settings.smallest_api_key:
        configured.append("smallest")
    if not configured:
        return ComponentHealth(
            status="degraded", detail="no AI provider keys configured; local fallbacks only"
        )
    return ComponentHealth(status="ok", detail="keys present (untested): " + ", ".join(configured))


def build_report(settings: Settings, version: str) -> HealthReport:
    components = {
        "database": check_database(settings),
        "ffmpeg": check_binary(settings.ffmpeg_bin, ["-version"]),
        "ffprobe": check_binary(settings.ffprobe_bin, ["-version"]),
        "tesseract": check_binary(settings.tesseract_bin, ["--version"]),
        "ai_providers": check_providers(settings),
    }
    statuses = {c.status for c in components.values()}
    critical_down = any(
        components[name].status == "down" for name in ("database", "ffmpeg", "ffprobe")
    )
    overall: Status = "down" if critical_down else ("degraded" if statuses - {"ok"} else "ok")
    return HealthReport(
        status=overall, version=version, environment=settings.app_env, components=components
    )
