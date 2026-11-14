"""Coverage and verification report (Task 28)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from seehere.api.errors import APIError
from seehere.db.models import Project
from seehere.db.session import get_db
from seehere.report.coverage import load_report

router = APIRouter(prefix="/api", tags=["report"])

DbDep = Annotated[Session, Depends(get_db)]


@router.get("/projects/{project_id}/report")
def get_report(project_id: uuid.UUID, db: DbDep) -> dict[str, Any]:
    """What happened to every visual on screen: described, skipped (with reason), held for
    review, rejected or said aloud, with verification and timing results."""
    if db.get(Project, project_id) is None:
        raise APIError(404, "not_found", "No project with this ID.")
    return load_report(db, project_id)
