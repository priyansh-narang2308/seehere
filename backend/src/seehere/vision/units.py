"""Visual units (Task 12): the meaningful things on each keyframe, with a box and a time span.
A slide shown more than once gets one unit per appearance, so each is scored on its own.

By default units are built from local evidence only: OCR lines on a keyframe are grouped into
text blocks by vertical proximity. With `VISION_PROVIDER=vultr` and an API key, each keyframe
is also sent to the vision model; its schema-validated units replace the OCR blocks for that
frame, and if the model fails validation twice the frame keeps its OCR blocks.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from seehere.core.config import Settings
from seehere.db.enums import MediaKind, VisualKind
from seehere.db.models import Frame, MediaAsset, OcrRegion, VisualUnit
from seehere.jobs import queue
from seehere.jobs.errors import PermanentJobError, RetryableJobError
from seehere.jobs.queue import ClaimedJob
from seehere.jobs.worker import JobContext
from seehere.providers.vision_vultr import VisionError, VisionOutputInvalid, VultrVisionAnalyzer
from seehere.vision.coverage import queue_coverage
from seehere.vision.schema import PROMPT, UNITS_SCHEMA

log = logging.getLogger("seehere.vision")

JOB_KIND = "visual.analyze"
OCR_SOURCE = "ocr"


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    w: float
    h: float

    def union(self, other: Box) -> Box:
        x, y = min(self.x, other.x), min(self.y, other.y)
        right = max(self.x + self.w, other.x + other.w)
        bottom = max(self.y + self.h, other.y + other.h)
        return Box(x, y, right - x, bottom - y)


@dataclass
class Unit:
    kind: VisualKind
    label: str
    box: Box
    lines: list[str]
    details: str = ""
    source: str = OCR_SOURCE
    extra: dict[str, Any] = field(default_factory=dict)

    def values(self) -> dict[str, Any]:
        out: dict[str, Any] = {"lines": self.lines}
        if self.details:
            out["details"] = self.details
        return out


def group_text_blocks(lines: list[tuple[str, Box]], gap: float = 1.0) -> list[Unit]:
    """Group OCR lines into blocks: a line joins the block above it when the vertical gap is
    at most `gap` times the taller line's height. Blocks are returned top to bottom."""
    blocks: list[list[tuple[str, Box]]] = []
    for text, box in sorted(lines, key=lambda line: (line[1].y, line[1].x)):
        if blocks:
            _, prev = blocks[-1][-1]
            if box.y - (prev.y + prev.h) <= gap * max(prev.h, box.h):
                blocks[-1].append((text, box))
                continue
        blocks.append([(text, box)])
    units = []
    for block in blocks:
        box = block[0][1]
        for _, b in block[1:]:
            box = box.union(b)
        texts = [t for t, _ in block]
        units.append(Unit(VisualKind.TEXT_BLOCK, texts[0][:200], box, texts))
    return units


def units_from_model(reply: dict[str, Any], source: str) -> list[Unit]:
    """Validated model output to units. Boxes are clipped to the frame."""
    out = []
    for u in reply["units"]:
        b = u["box"]
        x, y = min(b["x"], 1.0), min(b["y"], 1.0)
        box = Box(x, y, max(min(b["w"], 1.0 - x), 0.0), max(min(b["h"], 1.0 - y), 0.0))
        out.append(
            Unit(VisualKind(u["kind"]), u["label"], box, u["visible_text"], u["details"], source)
        )
    return out


def make_analyzer(settings: Settings) -> VultrVisionAnalyzer | None:
    """The vision model, only when explicitly enabled (each call costs credit)."""
    if settings.vision_provider != "vultr" or settings.vultr_inference_api_key is None:
        return None
    return VultrVisionAnalyzer(
        settings.vultr_inference_api_key,
        base_url=settings.vultr_inference_base_url,
        model=settings.vultr_vision_model,
        timeout_s=settings.vultr_vision_timeout_s,
    )


def queue_visual_analysis(session: Session, project_id: uuid.UUID) -> None:
    """Queue (or re-queue) visual analysis after on-screen text changed. Does not commit."""
    queue.enqueue_or_restart(
        session, project_id=project_id, kind=JOB_KIND, idempotency_key=f"{JOB_KIND}:{project_id}"
    )


def appearances(
    frames: list[tuple[float, int | None]], end_s: float
) -> dict[int, list[tuple[float, float]]]:
    """Time spans during which each scene is on screen, from sampled frames in time order:
    a scene that comes back (a revisited slide) gets one span per appearance."""
    spans: dict[int, list[tuple[float, float]]] = {}
    run_scene: int | None = None
    run_start = 0.0
    for t, scene in [*frames, (end_s, None)]:
        if scene != run_scene:
            if run_scene is not None:
                spans.setdefault(run_scene, []).append((run_start, t))
            run_scene, run_start = scene, t
    return spans


@dataclass(frozen=True)
class _Keyframe:
    id: uuid.UUID
    path: str
    spans: list[tuple[float, float]]
    lines: list[tuple[str, Box]]


def _keyframes(s: Session, project_id: uuid.UUID) -> list[_Keyframe]:
    video = s.scalars(
        select(MediaAsset).where(
            MediaAsset.project_id == project_id, MediaAsset.kind == MediaKind.SOURCE_VIDEO
        )
    ).first()
    if video is None:
        return []
    frames = list(
        s.execute(
            select(Frame.id, Frame.t_s, Frame.storage_path, Frame.is_keyframe, Frame.scene_index)
            .where(Frame.media_asset_id == video.id)
            .order_by(Frame.t_s)
        )
    )
    keys = [f for f in frames if f.is_keyframe and f.scene_index is not None]
    if not keys:
        return []
    # Frames are sampled at a fixed rate, so the last one stays up for one more step.
    step = frames[-1].t_s - frames[-2].t_s if len(frames) > 1 else 0.0
    end_s = max(video.duration_s or 0.0, frames[-1].t_s + step)
    spans = appearances([(f.t_s, f.scene_index) for f in frames], end_s)
    lines: dict[uuid.UUID, list[tuple[str, Box]]] = {k.id: [] for k in keys}
    for o in s.scalars(select(OcrRegion).where(OcrRegion.frame_id.in_(list(lines)))):
        lines[o.frame_id].append((o.text, Box(o.x, o.y, o.w, o.h)))
    return [_Keyframe(k.id, k.storage_path, spans[k.scene_index], lines[k.id]) for k in keys]


def analyze_visuals(ctx: JobContext, job: ClaimedJob) -> None:
    with ctx.session() as s:
        keyframes = _keyframes(s, job.project_id)
    if not keyframes:
        raise PermanentJobError("No keyframes were found. Run scene detection again.")

    analyzer = make_analyzer(ctx.settings)
    results: list[tuple[_Keyframe, list[Unit]]] = []
    for n, kf in enumerate(keyframes):
        ctx.progress("analyze", n / len(keyframes))
        units = group_text_blocks(kf.lines)
        if analyzer is not None:
            try:
                reply = analyzer.analyze(ctx.store.resolve(kf.path), PROMPT, UNITS_SCHEMA)
                units = units_from_model(reply, analyzer.info().name)
            except VisionOutputInvalid as exc:
                log.warning("frame %s: %s; keeping OCR blocks", kf.id, exc)
            except VisionError as exc:
                log.warning("vision request failed on frame %s: %s", kf.id, exc)
                raise RetryableJobError("The vision model could not be reached.") from exc
        results.append((kf, units))

    ctx.progress("save", 0.95)
    ctx.check_cancelled()
    with ctx.session() as s:
        s.execute(delete(VisualUnit).where(VisualUnit.project_id == job.project_id))
        s.add_all(
            VisualUnit(
                project_id=job.project_id,
                frame_id=kf.id,
                kind=u.kind,
                label=u.label,
                values=u.values(),
                x=u.box.x,
                y=u.box.y,
                w=u.box.w,
                h=u.box.h,
                t_start_s=start,
                t_end_s=end,
                source=u.source,
            )
            for kf, units in results
            for start, end in kf.spans
            for u in units
        )
        queue_coverage(s, job.project_id)
        s.commit()
    log.info(
        "project %s: %d visual units on %d keyframes",
        job.project_id,
        sum(len(u) * len(kf.spans) for kf, u in results),
        len(results),
    )
    ctx.progress("save", 1.0)
