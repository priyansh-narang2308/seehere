"""Performance, resource and provider-spend metrics (Task 33)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from seehere.api.errors import APIError
from seehere.core.config import Settings, get_settings
from seehere.db.models import Project
from seehere.db.session import get_db
from seehere.jobs import metrics

router = APIRouter(prefix="/api", tags=["metrics"])

DbDep = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.get("/metrics")
def get_metrics(db: DbDep, settings: SettingsDep) -> dict[str, Any]:
    """Run time per pipeline stage (median, 95th percentile, max), CPU, memory and hosted-model
    calls over every measured job still stored."""
    return metrics.summary(db, settings)


@router.get("/projects/{project_id}/metrics")
def get_project_metrics(project_id: uuid.UUID, db: DbDep, settings: SettingsDep) -> dict[str, Any]:
    """How long each step of this project took, what it used, and what it called."""
    if db.get(Project, project_id) is None:
        raise APIError(404, "not_found", "No project with this ID.")
    return metrics.project_metrics(db, settings, project_id)
