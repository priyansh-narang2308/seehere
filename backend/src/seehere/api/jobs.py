"""Job status and control, and the outputs of media preparation.

State-changing endpoints (cancel, retry) require the `X-SeeHere-Request: 1` header. A custom
header cannot be sent cross-site without a CORS preflight, which only the web app's origin
passes, so another website cannot make a visitor's browser cancel or restart jobs.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from seehere.api.errors import APIError
from seehere.core.config import Settings, get_settings
from seehere.db.enums import JobStatus, MediaKind
from seehere.db.models import Frame, Job, MediaAsset, Project
from seehere.db.session import get_db
from seehere.jobs import queue
from seehere.media.storage import MediaStore, UnsafePathError
from seehere.pipeline import JOB_LABELS

router = APIRouter(prefix="/api", tags=["jobs"])

DbDep = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def require_app_request(
    x_seehere_request: Annotated[str | None, Header()] = None,
) -> None:
    if x_seehere_request != "1":
        raise APIError(
            403, "missing_request_header", "This action needs the X-SeeHere-Request header."
        )


class JobOut(BaseModel):
    id: uuid.UUID
    kind: str
    label: str
    status: JobStatus
    stage: str | None
    progress: float
    attempts: int
    max_attempts: int
    cancel_requested: bool
    error: str | None
    created_at: datetime
    run_after: datetime
    finished_at: datetime | None

    @classmethod
    def from_model(cls, job: Job) -> JobOut:
        return cls(
            id=job.id,
            kind=job.kind,
            label=JOB_LABELS.get(job.kind, job.kind),
            status=job.status,
            stage=job.stage,
            progress=job.progress,
            attempts=job.attempts,
            max_attempts=job.max_attempts,
            cancel_requested=job.cancel_requested,
            error=job.error,
            created_at=job.created_at,
            run_after=job.run_after,
            finished_at=job.finished_at,
        )


class JobList(BaseModel):
    # The server's clock, so the client can tell how long a job has waited without trusting
    # its own clock.
    now: datetime
    jobs: list[JobOut]


def _project_or_404(db: Session, project_id: uuid.UUID) -> None:
    if db.get(Project, project_id) is None:
        raise APIError(404, "not_found", "No project with this ID.")


@router.get("/projects/{project_id}/jobs", response_model=JobList)
def list_jobs(project_id: uuid.UUID, db: DbDep) -> JobList:
    _project_or_404(db, project_id)
    jobs = db.scalars(select(Job).where(Job.project_id == project_id).order_by(Job.created_at))
    return JobList(
        now=db.execute(select(func.now())).scalar_one(), jobs=[JobOut.from_model(j) for j in jobs]
    )


def _job_or_404(db: Session, job_id: uuid.UUID) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise APIError(404, "not_found", "No job with this ID.")
    return job


@router.post(
    "/jobs/{job_id}/cancel", response_model=JobOut, dependencies=[Depends(require_app_request)]
)
def cancel_job(job_id: uuid.UUID, db: DbDep) -> JobOut:
    """Cancel a queued job now, or ask the worker to stop a running one."""
    job = _job_or_404(db, job_id)
    if job.status not in queue.ACTIVE:
        raise APIError(409, "not_active", "This job has already finished.")
    updated = queue.request_cancel(db, job_id)
    assert updated is not None
    queue.refresh_project_status(db, updated.project_id)
    return JobOut.from_model(updated)


@router.post(
    "/jobs/{job_id}/retry", response_model=JobOut, dependencies=[Depends(require_app_request)]
)
def retry_job(job_id: uuid.UUID, db: DbDep) -> JobOut:
    """Run a failed or cancelled job again from the start."""
    _job_or_404(db, job_id)
    updated = queue.retry(db, job_id)
    if updated is None:
        raise APIError(409, "not_retryable", "Only failed or cancelled jobs can be run again.")
    queue.refresh_project_status(db, updated.project_id)
    return JobOut.from_model(updated)


class AudioOut(BaseModel):
    duration_s: float | None
    sample_rate: int
    channels: int
    size_bytes: int


class FrameOut(BaseModel):
    id: uuid.UUID
    t_s: float


class FramesOut(BaseModel):
    count: int
    fps: float | None
    first_s: float | None
    last_s: float | None
    preview: list[FrameOut]


class KeyframeOut(BaseModel):
    id: uuid.UUID
    t_s: float
    scene_index: int


class ScenesOut(BaseModel):
    """Result of scene detection: the first appearance of each distinct picture, in order,
    and how many times an earlier one came back."""

    keyframes: list[KeyframeOut]
    revisits: int


class PreparedMedia(BaseModel):
    audio: AudioOut | None
    frames: FramesOut
    scenes: ScenesOut | None = None  # None until scene detection has run


@router.get("/projects/{project_id}/media", response_model=PreparedMedia)
def prepared_media(project_id: uuid.UUID, db: DbDep, preview: int = 12) -> PreparedMedia:
    """What media preparation produced. `preview` frames are spread evenly over the video."""
    _project_or_404(db, project_id)
    preview = max(0, min(preview, 48))
    audio = db.scalars(
        select(MediaAsset).where(
            MediaAsset.project_id == project_id, MediaAsset.kind == MediaKind.NORMALIZED_AUDIO
        )
    ).first()
    frames = list(
        db.execute(
            select(Frame.id, Frame.t_s, Frame.is_keyframe, Frame.scene_index, Frame.phash)
            .join(MediaAsset, Frame.media_asset_id == MediaAsset.id)
            .where(MediaAsset.project_id == project_id)
            .order_by(Frame.t_s)
        )
    )
    probe = (audio.probe or {}) if audio else {}
    scenes = None
    if frames and all(f.phash for f in frames):
        keyframes = [
            KeyframeOut(id=f.id, t_s=f.t_s, scene_index=f.scene_index or 0)
            for f in frames
            if f.is_keyframe
        ]
        changes = sum(
            1 for a, b in zip(frames, frames[1:], strict=False) if a.scene_index != b.scene_index
        )
        scenes = ScenesOut(keyframes=keyframes, revisits=changes + 1 - len(keyframes))
    picked = (
        [frames[round(i * (len(frames) - 1) / max(preview - 1, 1))] for i in range(preview)]
        if len(frames) > preview
        else frames
    )
    return PreparedMedia(
        audio=AudioOut(
            duration_s=audio.duration_s,
            sample_rate=int(probe.get("sample_rate", 0)),
            channels=int(probe.get("channels", 0)),
            size_bytes=audio.size_bytes,
        )
        if audio
        else None,
        frames=FramesOut(
            count=len(frames),
            fps=probe.get("frames", {}).get("fps"),
            first_s=frames[0].t_s if frames else None,
            last_s=frames[-1].t_s if frames else None,
            preview=[FrameOut(id=f.id, t_s=f.t_s) for f in dict.fromkeys(picked)],
        ),
        scenes=scenes,
    )


@router.get("/frames/{frame_id}/image", response_class=FileResponse)
def frame_image(frame_id: uuid.UUID, db: DbDep, settings: SettingsDep) -> FileResponse:
    frame = db.get(Frame, frame_id)
    if frame is None:
        raise APIError(404, "not_found", "No frame with this ID.")
    try:
        path = MediaStore(settings.media_dir).resolve(frame.storage_path)
    except UnsafePathError as exc:
        raise APIError(404, "not_found", "No frame with this ID.") from exc
    if not path.is_file():
        raise APIError(404, "not_found", "The frame image is no longer stored.")
    return FileResponse(
        path,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "private, max-age=3600",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": "inline",
        },
    )
