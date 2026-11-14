"""Export files: list them and download one."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from seehere.api.errors import APIError
from seehere.core.config import Settings, get_settings
from seehere.db.enums import ExportKind
from seehere.db.models import ExportArtifact, Project
from seehere.db.session import get_db
from seehere.media.storage import MediaStore, UnsafePathError

router = APIRouter(prefix="/api", tags=["exports"])

DbDep = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]

MEDIA_TYPES = {
    ExportKind.WEBVTT: "text/vtt",
    ExportKind.CUE_AUDIO_ZIP: "application/zip",
    ExportKind.STANDARD_MP4: "video/mp4",
    ExportKind.EXTENDED_MP4: "video/mp4",
    ExportKind.TRANSCRIPT_HTML: "text/html",
    ExportKind.MANIFEST_JSON: "application/json",
    ExportKind.REPORT_HTML: "text/html",
    ExportKind.REPORT_JSON: "application/json",
    ExportKind.BUNDLE_ZIP: "application/zip",
}


class ExportOut(BaseModel):
    id: uuid.UUID
    kind: ExportKind
    filename: str
    size_bytes: int
    sha256: str
    url: str
    created_at: datetime


class ExportsOut(BaseModel):
    available: bool
    files: list[ExportOut] = []


@router.get("/projects/{project_id}/exports", response_model=ExportsOut)
def list_exports(project_id: uuid.UUID, db: DbDep) -> ExportsOut:
    if db.get(Project, project_id) is None:
        raise APIError(404, "not_found", "No project with this ID.")
    rows = list(
        db.scalars(
            select(ExportArtifact)
            .where(ExportArtifact.project_id == project_id)
            .order_by(ExportArtifact.kind)
        )
    )
    return ExportsOut(
        available=bool(rows),
        files=[
            ExportOut(
                id=a.id,
                kind=a.kind,
                filename=a.storage_path.rsplit("/", 1)[-1],
                size_bytes=a.size_bytes,
                sha256=a.sha256,
                url=f"/api/exports/{a.id}",
                created_at=a.created_at,
            )
            for a in rows
        ],
    )


@router.get("/exports/{export_id}", response_class=FileResponse)
def download_export(
    export_id: uuid.UUID, db: DbDep, settings: SettingsDep, inline: bool = False
) -> FileResponse:
    art = db.get(ExportArtifact, export_id)
    if art is None:
        raise APIError(404, "not_found", "No export with this ID.")
    try:
        path = MediaStore(settings.media_dir).resolve(art.storage_path)
    except UnsafePathError as exc:
        raise APIError(404, "not_found", "No export with this ID.") from exc
    if not path.is_file():
        raise APIError(404, "not_found", "The export file is no longer stored.")
    # HTML is always downloaded, never rendered in our origin.
    disposition = "inline" if inline and MEDIA_TYPES[art.kind] != "text/html" else "attachment"
    return FileResponse(
        path,
        media_type=MEDIA_TYPES[art.kind],
        filename=path.name,
        content_disposition_type=disposition,
        headers={"Cache-Control": "private, max-age=600", "X-Content-Type-Options": "nosniff"},
    )
