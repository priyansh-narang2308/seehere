"""Visual units (Task 12): the meaningful things on each keyframe, with a box and a time span.
A slide shown more than once gets one unit per appearance, so each is scored on its own.

By default units are built from local evidence only: OCR lines on a keyframe are grouped into
text blocks by vertical proximity. With `VISION_PROVIDER=vultr` and an API key, each keyframe
is also sent to the vision model; its schema-validated units replace the OCR blocks for that
frame, and if the model fails validation twice the frame keeps its OCR blocks.
"""

from __future__ import annotations

import contextvars
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
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
from seehere.providers.errors import job_error
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


VISION_SERVICE = {"vultr": "The Vultr vision model", "gemini": "The Gemini vision model"}


def make_analyzer(settings: Settings) -> VultrVisionAnalyzer | None:
    """The vision model, only when explicitly enabled (each call costs credit or quota)."""
    if settings.vision_provider == "vultr" and settings.vultr_inference_api_key is not None:
        return VultrVisionAnalyzer(
            settings.vultr_inference_api_key,
            base_url=settings.vultr_inference_base_url,
            model=settings.vultr_vision_model,
            timeout_s=settings.vultr_vision_timeout_s,
        )
    if settings.vision_provider == "gemini" and settings.gemini_api_key is not None:
        return VultrVisionAnalyzer(
            settings.gemini_api_key,
            base_url=settings.gemini_base_url,
            model=settings.gemini_vision_model,
            timeout_s=settings.vultr_vision_timeout_s,
            service="gemini",
            schema_in_prompt=True,
        )
    return None


def _ask_model(
    ctx: JobContext, analyzer: VultrVisionAnalyzer, keyframes: list[_Keyframe]
) -> dict[uuid.UUID, list[Unit]]:
    """Ask the vision model about every keyframe, a few at a time. A keyframe whose reply is
    invalid twice keeps its OCR blocks; any request failure stops the job (classified by
    `job_error`). Each request runs in a copy of this context, so it is metered for this job."""
    found: dict[uuid.UUID, list[Unit]] = {}
    workers = max(1, min(ctx.settings.vision_concurrency, len(keyframes)))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="vision") as pool:
        futures = {
            pool.submit(
                contextvars.copy_context().run,
                analyzer.analyze,
                ctx.store.resolve(kf.path),
                PROMPT,
                UNITS_SCHEMA,
            ): kf
            for kf in keyframes
        }
        try:
            for done, future in enumerate(as_completed(futures), start=1):
                kf = futures[future]
                try:
                    found[kf.id] = units_from_model(future.result(), analyzer.info().name)
                except VisionOutputInvalid as exc:
                    log.warning("frame %s: %s; keeping OCR blocks", kf.id, exc)
                except VisionError as exc:
                    log.warning("vision request failed on frame %s: %s", kf.id, exc)
                    hint = "Check GEMINI_API_KEY" if analyzer.service == "gemini" else None
                    raise job_error(
                        exc, VISION_SERVICE.get(analyzer.service, "The vision model"), hint
                    ) from None
                ctx.progress("analyze", done / len(keyframes))
        finally:
            for future in futures:  # stop queued requests after a failure or cancellation
                future.cancel()
    return found


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
    units_by_frame = {kf.id: group_text_blocks(kf.lines) for kf in keyframes}
    if analyzer is not None:
        try:
            units_by_frame.update(_ask_model(ctx, analyzer, keyframes))
        except RetryableJobError as exc:
            if job.attempts < job.max_attempts:
                raise  # try the model again after the backoff
            # The model stayed unavailable (outage or quota) on the last attempt: keep the
            # OCR units, which every later stage can work from, rather than fail the lecture.
            # A rejected key is a PermanentJobError and still fails loudly.
            log.warning(
                "vision model unavailable after %d attempts (%s); OCR units kept",
                job.attempts,
                exc.message,
            )
            ctx.progress("ocr-only", 0.9)
    results = [(kf, units_by_frame[kf.id]) for kf in keyframes]

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
