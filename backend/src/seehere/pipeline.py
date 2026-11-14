"""The processing pipeline: which job kinds exist and which handler runs each one.

A stage gets a handler here only once it is implemented and tested.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from seehere.describe import generate, verify
from seehere.export import build
from seehere.jobs import queue
from seehere.jobs.worker import Handler
from seehere.media import normalize, ocr, scenes
from seehere.references import resolve
from seehere.schedule import plan, timing
from seehere.slides import ingest
from seehere.speech import synthesize, transcribe
from seehere.vision import coverage, units

HANDLERS: dict[str, Handler] = {
    normalize.JOB_KIND: normalize.prepare_media,
    transcribe.JOB_KIND: transcribe.transcribe_speech,
    scenes.JOB_KIND: scenes.detect_scene_changes,
    ocr.JOB_KIND: ocr.extract_text,
    ingest.JOB_KIND: ingest.ingest_deck,
    units.JOB_KIND: units.analyze_visuals,
    coverage.JOB_KIND: coverage.score_coverage,
    resolve.JOB_KIND: resolve.resolve_references,
    generate.JOB_KIND: generate.generate_descriptions,
    verify.JOB_KIND: verify.verify_claims,
    plan.JOB_KIND: plan.plan_schedule,
    synthesize.JOB_KIND: synthesize.synthesize_speech,
    timing.JOB_KIND: timing.check_timing,
    build.JOB_KIND: build.build_export,
}

# What each job kind is called in the UI.
JOB_LABELS = {
    normalize.JOB_KIND: "Media preparation",
    transcribe.JOB_KIND: "Speech-to-text",
    scenes.JOB_KIND: "Scene and slide changes",
    ocr.JOB_KIND: "On-screen text",
    ingest.JOB_KIND: "Slide deck",
    units.JOB_KIND: "Visual analysis",
    coverage.JOB_KIND: "Seen versus said",
    resolve.JOB_KIND: "Visual references",
    generate.JOB_KIND: "Descriptions",
    verify.JOB_KIND: "Claim verification",
    plan.JOB_KIND: "Scheduling",
    synthesize.JOB_KIND: "Speech synthesis",
    timing.JOB_KIND: "Timing check",
    build.JOB_KIND: "Export",
}


def start_pipeline(session: Session, project_id: uuid.UUID, media_id: uuid.UUID) -> None:
    """Queue the first stage for a newly stored source video. Does not commit: the caller
    commits it together with the upload, so a project never exists without its job."""
    queue.enqueue(
        session,
        project_id=project_id,
        kind=normalize.JOB_KIND,
        idempotency_key=f"{normalize.JOB_KIND}:{media_id}",
    )
