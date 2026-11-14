"""Scene and slide change detection (pipeline stage "scenes", job kind `scenes.detect`).

Works on the frames media preparation sampled (one per second by default):

1. Each frame becomes a small grayscale thumbnail (64x36).
2. A frame is a **keyframe** when it differs from the previous keyframe in at least
   `scene_change_fraction` of its thumbnail pixels (each by more than `scene_pixel_delta` of 255
   levels) **and** the picture has settled: the next frame is nearly the same. So a slide
   transition or animation yields one keyframe on the finished slide, not one per step, and slow
   drift is caught because each frame is compared with the last keyframe, not only its neighbour.
3. **Dedupe:** a keyframe that matches an earlier scene by the same test (a slide shown again)
   gets that scene's index and is not marked as a new keyframe, so it is not described twice.

Every frame stores its `scene_index`; first appearances have `is_keyframe = true`; `phash` holds
a 64-bit difference hash for later matching. The handler rewrites all of this on every run, so
re-running is idempotent. The thresholds are plain settings, checked against a synthetic lecture
with known slide changes in `tests/test_scenes.py`.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt
from PIL import Image
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from seehere.db.enums import MediaKind
from seehere.db.models import Frame, MediaAsset
from seehere.jobs import queue
from seehere.jobs.errors import PermanentJobError
from seehere.jobs.queue import ClaimedJob
from seehere.jobs.worker import JobContext

log = logging.getLogger("seehere.scenes")

JOB_KIND = "scenes.detect"
THUMB = (64, 36)

Thumb = npt.NDArray[np.int16]


def thumbnail(path: Path) -> Thumb:
    with Image.open(path) as im:
        im.draft("L", (THUMB[0] * 2, THUMB[1] * 2))  # fast JPEG downscale while decoding
        small = im.convert("L").resize(THUMB, Image.Resampling.BOX)
        return np.asarray(small, dtype=np.int16)


def dhash(thumb: Thumb) -> str:
    """64-bit difference hash (9x8 gradient signs), as 16 hex digits."""
    small = Image.fromarray(thumb.astype(np.uint8)).resize((9, 8), Image.Resampling.BOX)
    a = np.asarray(small, dtype=np.int16)
    bits = (a[:, 1:] > a[:, :-1]).flatten()
    return f"{int(''.join('1' if b else '0' for b in bits), 2):016x}"


def changed_fraction(a: Thumb, b: Thumb, pixel_delta: int) -> float:
    return float(np.mean(np.abs(a - b) > pixel_delta))


@dataclass(frozen=True)
class SceneResult:
    scene_index: list[int]  # per frame
    keyframes: list[int]  # frame positions that start a new (first-seen) scene
    revisits: list[int]  # frame positions where an earlier scene came back


def detect_scenes(thumbs: list[Thumb], *, fraction: float, pixel_delta: int) -> SceneResult:
    if not thumbs:
        return SceneResult([], [], [])

    def differs(a: Thumb, b: Thumb) -> bool:
        return changed_fraction(a, b, pixel_delta) >= fraction

    scenes: list[Thumb] = [thumbs[0]]  # representative thumbnail of each distinct scene
    current = 0
    anchor = thumbs[0]
    index = [0]
    keyframes, revisits = [0], []
    for i in range(1, len(thumbs)):
        settled = i + 1 == len(thumbs) or not differs(thumbs[i], thumbs[i + 1])
        if differs(anchor, thumbs[i]) and settled:
            anchor = thumbs[i]
            match = next(
                (k for k, s in enumerate(scenes) if k != current and not differs(s, thumbs[i])),
                None,
            )
            if match is None:
                scenes.append(thumbs[i])
                current = len(scenes) - 1
                keyframes.append(i)
            else:
                current = match
                revisits.append(i)
        index.append(current)
    return SceneResult(index, keyframes, revisits)


def queue_scene_detection(session: Session, project_id: uuid.UUID) -> None:
    """Queue (or re-queue) scene detection after new frames were saved. Does not commit."""
    queue.enqueue_or_restart(
        session,
        project_id=project_id,
        kind=JOB_KIND,
        idempotency_key=f"{JOB_KIND}:{project_id}",
    )


def detect_scene_changes(ctx: JobContext, job: ClaimedJob) -> None:
    with ctx.session() as s:
        rows = list(
            s.execute(
                select(Frame.id, Frame.storage_path)
                .join(MediaAsset, Frame.media_asset_id == MediaAsset.id)
                .where(
                    MediaAsset.project_id == job.project_id,
                    MediaAsset.kind == MediaKind.SOURCE_VIDEO,
                )
                .order_by(Frame.t_s)
            )
        )
    if not rows:
        raise PermanentJobError("No sampled frames were found. Run media preparation again.")

    ctx.progress("compare", 0.0)
    thumbs: list[Thumb] = []
    for n, (_, rel) in enumerate(rows):
        try:
            thumbs.append(thumbnail(ctx.store.resolve(rel)))
        except (OSError, ValueError) as exc:
            raise PermanentJobError("A sampled frame could not be read.") from exc
        if n % 50 == 0:
            ctx.progress("compare", 0.9 * n / len(rows))

    cfg = ctx.settings
    result = detect_scenes(
        thumbs, fraction=cfg.scene_change_fraction, pixel_delta=cfg.scene_pixel_delta
    )
    keyframes = set(result.keyframes)
    ctx.progress("save", 0.95)
    ctx.check_cancelled()
    with ctx.session() as s:
        for pos, (frame_id, _) in enumerate(rows):
            s.execute(
                update(Frame)
                .where(Frame.id == frame_id)
                .values(
                    is_keyframe=pos in keyframes,
                    scene_index=result.scene_index[pos],
                    phash=dhash(thumbs[pos]),
                )
            )
        s.commit()
    log.info(
        "project %s: %d frames, %d keyframes, %d revisits",
        job.project_id,
        len(rows),
        len(result.keyframes),
        len(result.revisits),
    )
    ctx.progress("save", 1.0)
