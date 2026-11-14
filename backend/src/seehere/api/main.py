"""SeeHere HTTP API (FastAPI)."""

from __future__ import annotations

from importlib.metadata import version as pkg_version

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from seehere.api.cues import router as cues_router
from seehere.api.deck import router as deck_router
from seehere.api.errors import install_error_handlers
from seehere.api.health import HealthReport, build_report
from seehere.api.jobs import router as jobs_router
from seehere.api.ocr import router as ocr_router
from seehere.api.projects import router as projects_router
from seehere.api.transcript import router as transcript_router
from seehere.api.visuals import router as visuals_router
from seehere.core.config import get_settings

VERSION = pkg_version("seehere")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="SeeHere API",
        version=VERSION,
        description="Evidence-grounded audio descriptions for lecture videos.",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.api_cors_origins.split(",") if o.strip()],
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["*"],
    )
    install_error_handlers(app)
    app.include_router(projects_router)
    app.include_router(jobs_router)
    app.include_router(transcript_router)
    app.include_router(ocr_router)
    app.include_router(deck_router)
    app.include_router(visuals_router)
    app.include_router(cues_router)

    @app.get("/api/health/live", tags=["health"])
    def live() -> dict[str, str]:
        """Liveness: the process is up. Used by Docker/Caddy health checks."""
        return {"status": "ok"}

    @app.get("/api/health", response_model=HealthReport, tags=["health"])
    def health(response: Response) -> HealthReport:
        """Readiness: database, media binaries and provider configuration."""
        report = build_report(get_settings(), VERSION)
        if report.status == "down":
            response.status_code = 503
        return report

    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("seehere.api.main:app", host="127.0.0.1", port=8000, reload=True)
