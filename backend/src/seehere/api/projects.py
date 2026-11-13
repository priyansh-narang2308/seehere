"""Projects and the secure upload endpoint.

Upload protocol: `POST /api/projects` with the raw video as the request body (not multipart).
Metadata travels in headers, URL-encoded so any Unicode title is safe in a header:

    X-SeeHere-Title:            the lecture title (required, 1-200 characters)
    X-SeeHere-Filename:         the original filename (display only)
    X-SeeHere-Rights-Confirmed: "true" (required: the uploader owns or may process the video)

The body is streamed to a private temp file in 1 MiB chunks while its size and SHA-256 are
counted, so memory use is constant and the size cap is enforced before the whole file arrives.
The file is then identified by content with ffprobe. Only an accepted video is moved into place,
and the project and its media row are committed together; any failure removes the file.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated
from urllib.parse import unquote

import anyio
from fastapi import APIRouter, Depends, Header, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from seehere.api.errors import APIError
from seehere.core.config import Settings, get_settings
from seehere.db.enums import MediaKind, ProjectStatus
from seehere.db.models import MediaAsset, Project
from seehere.db.session import get_db
from seehere.media.probe import VideoProbe, inspect_lecture_video
from seehere.media.storage import MediaStore, sanitize_filename, source_video_path

router = APIRouter(prefix="/api", tags=["projects"])

ACCEPT = "video/mp4,video/quicktime,video/webm,video/x-matroska,.mp4,.mov,.webm,.mkv"


class UploadConfig(BaseModel):
    max_upload_bytes: int
    max_video_duration_s: int
    accept: str
    formats: list[str]


class MediaOut(BaseModel):
    original_filename: str
    mime_type: str
    size_bytes: int
    duration_s: float | None
    width: int | None
    height: int | None
    video_codec: str | None
    audio_codec: str | None


class ProjectOut(BaseModel):
    id: uuid.UUID
    title: str
    status: ProjectStatus
    created_at: datetime
    expires_at: datetime | None
    source: MediaOut | None

    @classmethod
    def from_model(cls, project: Project) -> ProjectOut:
        source = next((m for m in project.media if m.kind is MediaKind.SOURCE_VIDEO), None)
        return cls(
            id=project.id,
            title=project.title,
            status=project.status,
            created_at=project.created_at,
            expires_at=project.expires_at,
            source=MediaOut.model_validate(source, from_attributes=True) if source else None,
        )


SettingsDep = Annotated[Settings, Depends(get_settings)]
DbDep = Annotated[Session, Depends(get_db)]


@router.get("/config/upload", response_model=UploadConfig)
def upload_config(settings: SettingsDep) -> UploadConfig:
    """The real limits, so the web app never hard-codes them."""
    return UploadConfig(
        max_upload_bytes=settings.max_upload_bytes,
        max_video_duration_s=settings.max_video_duration_s,
        accept=ACCEPT,
        formats=["MP4", "MOV", "WebM", "MKV"],
    )


def _header_text(value: str | None, name: str) -> str:
    if value is None:
        raise APIError(400, "missing_header", f"The {name} header is required.")
    try:
        return unquote(value, errors="strict")
    except UnicodeDecodeError as exc:
        raise APIError(400, "invalid_header", f"The {name} header is not valid UTF-8.") from exc


@router.post("/projects", status_code=201, response_model=ProjectOut)
async def create_project(
    request: Request,
    settings: SettingsDep,
    db: DbDep,
    x_seehere_title: Annotated[str | None, Header()] = None,
    x_seehere_filename: Annotated[str | None, Header()] = None,
    x_seehere_rights_confirmed: Annotated[str | None, Header()] = None,
) -> ProjectOut:
    # 1. Cheap checks first, before reading a single byte of the body.
    if x_seehere_rights_confirmed != "true":
        raise APIError(
            400,
            "rights_not_confirmed",
            "Confirm that you own this video or have permission to process it.",
        )
    title = _header_text(x_seehere_title, "X-SeeHere-Title").strip()
    if not 1 <= len(title) <= 200:
        raise APIError(400, "invalid_title", "Enter a title between 1 and 200 characters.")
    filename = sanitize_filename(_header_text(x_seehere_filename, "X-SeeHere-Filename"))

    cap = settings.max_upload_bytes
    limit_text = f"The limit is {settings.max_upload_mb} MB."
    declared = request.headers.get("content-length")
    if declared is not None:
        if not declared.isdigit():
            raise APIError(400, "invalid_length", "Invalid Content-Length.")
        if int(declared) > cap:
            raise APIError(413, "too_large", f"The file is too large. {limit_text}")

    # 2. Stream the body to a private temp file, enforcing the cap as bytes arrive.
    store = MediaStore(settings.media_dir)
    temp = await run_in_threadpool(store.new_temp_file)
    try:
        digest = hashlib.sha256()
        size = 0
        async with await anyio.open_file(temp, "wb") as out:
            async for chunk in request.stream():
                size += len(chunk)
                if size > cap:
                    raise APIError(413, "too_large", f"The file is too large. {limit_text}")
                digest.update(chunk)
                await out.write(chunk)
        if size == 0:
            raise APIError(400, "empty_file", "The file is empty.")

        # 3. Identify by content, then 4. persist atomically.
        probe = await run_in_threadpool(inspect_lecture_video, temp, settings)
        project = await run_in_threadpool(
            _persist, db, store, temp, settings, title, filename, size, digest.hexdigest(), probe
        )
    finally:
        await run_in_threadpool(lambda: temp.unlink(missing_ok=True))
    return ProjectOut.from_model(project)


def _persist(
    db: Session,
    store: MediaStore,
    temp: Path,
    settings: Settings,
    title: str,
    filename: str,
    size: int,
    sha256: str,
    probe: VideoProbe,
) -> Project:
    now = datetime.now(UTC)
    project = Project(
        id=uuid.uuid4(),
        title=title,
        status=ProjectStatus.UPLOADED,
        rights_confirmed_at=now,
        expires_at=now + timedelta(hours=settings.media_retention_hours),
    )
    relative = source_video_path(project.id, probe.extension)
    project.media.append(
        MediaAsset(
            kind=MediaKind.SOURCE_VIDEO,
            original_filename=filename,
            storage_path=relative,
            mime_type=probe.mime_type,
            size_bytes=size,
            sha256=sha256,
            duration_s=probe.duration_s,
            width=probe.width,
            height=probe.height,
            video_codec=probe.video_codec,
            audio_codec=probe.audio_codec,
            probe=probe.raw,
        )
    )
    db.add(project)
    db.flush()
    dest = store.promote(temp, relative)
    os.chmod(dest, 0o600)
    try:
        db.commit()
    except Exception:
        store.remove(relative)
        raise
    return project


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(db: DbDep) -> list[ProjectOut]:
    projects = db.scalars(
        select(Project)
        .options(selectinload(Project.media))
        .order_by(Project.created_at.desc())
        .limit(100)
    ).all()
    return [ProjectOut.from_model(p) for p in projects]


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: uuid.UUID, db: DbDep) -> ProjectOut:
    project = db.scalar(
        select(Project).options(selectinload(Project.media)).where(Project.id == project_id)
    )
    if project is None:
        raise APIError(404, "not_found", "No project with this ID.")
    return ProjectOut.from_model(project)
