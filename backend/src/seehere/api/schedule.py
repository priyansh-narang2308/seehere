"""The chosen schedule for a mode: speech windows, placed cues (with any inserted pause and its
reason), why others were not placed, and the greedy versus CP-SAT comparison."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from seehere.api.errors import APIError
from seehere.core.config import Settings, get_settings
from seehere.db.enums import (
    DescriptionMode,
    DescriptionVariant,
    ScheduleStatus,
    SolverKind,
    VerificationState,
)
from seehere.db.models import AudioClip, DescriptionCue, Project, SchedulePlacement, ScheduleRun
from seehere.db.session import get_db
from seehere.media.storage import MediaStore, UnsafePathError

router = APIRouter(prefix="/api", tags=["schedule"])

DbDep = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


class WindowOut(BaseModel):
    start_s: float
    end_s: float


class PlacementOut(BaseModel):
    cue_id: uuid.UUID
    variant: DescriptionVariant
    text: str
    start_s: float
    end_s: float
    verification_state: VerificationState
    pause_s: float = 0.0
    audio_url: str | None = None  # the synthesized wording, once speech synthesis has run
    audio_s: float | None = None  # measured from the audio file
    pause_reason: str | None = None


class NotPlacedOut(BaseModel):
    cue_id: uuid.UUID
    text: str
    reason: str


class ScheduleOut(BaseModel):
    available: bool
    solver: SolverKind | None = None
    mode: DescriptionMode | None = None
    status: ScheduleStatus | None = None
    windows: list[WindowOut] = []
    placements: list[PlacementOut] = []
    not_placed: list[NotPlacedOut] = []
    priority_placed_share: float | None = None
    duration_ms: float | None = None
    pause_budget_s: float | None = None
    paused_s: float | None = None
    extended_duration_s: float | None = None
    comparison: dict[str, dict[str, Any]] | None = None


_HELD = "needs review: held back until an instructor approves it"


@router.get("/projects/{project_id}/schedule", response_model=ScheduleOut)
def get_schedule(
    project_id: uuid.UUID,
    db: DbDep,
    mode: Annotated[DescriptionMode, Query()] = DescriptionMode.STANDARD,
) -> ScheduleOut:
    if db.get(Project, project_id) is None:
        raise APIError(404, "not_found", "No project with this ID.")
    runs = list(
        db.scalars(
            select(ScheduleRun)
            .where(ScheduleRun.project_id == project_id, ScheduleRun.mode == mode)
            .order_by(ScheduleRun.created_at.desc())
        )
    )
    run = next((r for r in runs if r.metrics.get("selected")), runs[0] if runs else None)
    if run is None:
        return ScheduleOut(available=False)
    cues = {
        c.id: c
        for c in db.scalars(select(DescriptionCue).where(DescriptionCue.project_id == project_id))
    }
    texts = {
        DescriptionVariant.SHORT: lambda c: c.text_short,
        DescriptionVariant.MEDIUM: lambda c: c.text_medium,
        DescriptionVariant.LONG: lambda c: c.text_long,
    }
    clips = {
        (a.cue_id, a.variant): a
        for a in db.scalars(select(AudioClip).where(AudioClip.cue_id.in_(list(cues))))
    }
    placements = []
    for p in db.scalars(
        select(SchedulePlacement)
        .where(SchedulePlacement.run_id == run.id)
        .order_by(SchedulePlacement.start_s)
    ):
        cue = cues[p.cue_id]
        clip = clips.get((p.cue_id, p.variant))
        placements.append(
            PlacementOut(
                cue_id=p.cue_id,
                variant=p.variant,
                text=texts[p.variant](cue) or cue.text_short,
                start_s=p.start_s,
                end_s=p.end_s,
                verification_state=cue.verification_state,
                pause_s=p.inserted_pause_s,
                pause_reason=p.pause_reason,
                audio_url=f"/api/audio/{clip.id}" if clip else None,
                audio_s=clip.duration_s if clip else None,
            )
        )
    m = run.metrics
    not_placed = [
        NotPlacedOut(cue_id=cid, text=cues[cid].text_short, reason=reason)
        for cid, reason in [
            *((uuid.UUID(k["cue_id"]), k["reason"]) for k in m.get("skipped", [])),
            *((uuid.UUID(k), _HELD) for k in m.get("held_for_review", [])),
        ]
        if cid in cues
    ]
    return ScheduleOut(
        available=True,
        solver=run.solver,
        mode=run.mode,
        status=run.status,
        windows=[WindowOut(start_s=a, end_s=b) for a, b in m.get("windows", [])],
        placements=placements,
        not_placed=sorted(not_placed, key=lambda n: cues[n.cue_id].anchor_t_s),
        priority_placed_share=m.get("priority_placed_share"),
        duration_ms=run.duration_ms,
        pause_budget_s=m.get("budget_s"),
        paused_s=m.get("paused_s"),
        extended_duration_s=m.get("extended_duration_s"),
        comparison=m.get("comparison"),
    )


@router.get("/audio/{clip_id}", response_class=FileResponse)
def audio_clip(clip_id: uuid.UUID, db: DbDep, settings: SettingsDep) -> FileResponse:
    clip = db.get(AudioClip, clip_id)
    if clip is None:
        raise APIError(404, "not_found", "No audio clip with this ID.")
    try:
        path = MediaStore(settings.media_dir).resolve(clip.storage_path)
    except UnsafePathError as exc:
        raise APIError(404, "not_found", "No audio clip with this ID.") from exc
    if not path.is_file():
        raise APIError(404, "not_found", "The audio clip is no longer stored.")
    return FileResponse(
        path,
        media_type="audio/wav",
        headers={
            "Cache-Control": "private, max-age=3600",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": "inline",
        },
    )
