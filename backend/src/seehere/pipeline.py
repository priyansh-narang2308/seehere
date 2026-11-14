"""The processing pipeline: which job kinds exist and which handler runs each one.

A stage gets a handler here only once it is implemented and tested.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from seehere.jobs import queue
from seehere.jobs.worker import Handler
from seehere.media import normalize, scenes
from seehere.speech import transcribe

HANDLERS: dict[str, Handler] = {
    normalize.JOB_KIND: normalize.prepare_media,
    transcribe.JOB_KIND: transcribe.transcribe_speech,
    scenes.JOB_KIND: scenes.detect_scene_changes,
}

# What each job kind is called in the UI.
JOB_LABELS = {
    normalize.JOB_KIND: "Media preparation",
    transcribe.JOB_KIND: "Speech-to-text",
    scenes.JOB_KIND: "Scene and slide changes",
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
