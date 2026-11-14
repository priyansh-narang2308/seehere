"""On-screen text with Tesseract (pipeline stage "ocr", job kind `ocr.extract`).

Runs on keyframes only (Task 09): one per distinct picture, so a revisited slide is read once.

For each keyframe the image is converted to grayscale and enlarged 2x when small (Tesseract reads
small slide text much better that way), then `tesseract ... tsv` gives every word with its box
and confidence. Words are grouped into lines; each line becomes an `ocr_region` with its text,
mean confidence (0..1) and box as fractions of the frame (0..1), so boxes survive any resize.

The text is stored exactly as read. OCR is evidence with a confidence, not verified fact: it can
misread characters, miss stylized text and read text inside photos. Number repairs for comparison
live in `seehere.text.numbers` and are applied when comparing, not to the stored evidence.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

from PIL import Image
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from seehere.core.config import Settings
from seehere.db.enums import MediaKind
from seehere.db.models import Frame, MediaAsset, OcrRegion
from seehere.jobs import queue
from seehere.jobs.errors import PermanentJobError, RetryableJobError
from seehere.jobs.queue import ClaimedJob
from seehere.jobs.worker import JobContext
from seehere.slides.ingest import has_deck, queue_deck_ingest
from seehere.vision.units import queue_visual_analysis

log = logging.getLogger("seehere.ocr")

JOB_KIND = "ocr.extract"
UPSCALE_BELOW_WIDTH = 1600


class OcrError(RuntimeError):
    pass


@dataclass(frozen=True)
class OcrLine:
    text: str
    confidence: float  # 0..1, mean of the words
    x: float  # box as fractions of the image
    y: float
    w: float
    h: float


def parse_tsv(tsv: str, width: int, height: int, min_confidence: float) -> list[OcrLine]:
    """Group Tesseract TSV words (level 5) into lines with a box and mean confidence."""
    lines: dict[tuple[str, ...], list[tuple[int, int, int, int, float, str]]] = {}
    for row in tsv.splitlines()[1:]:
        cols = row.split("\t", 11)
        if len(cols) < 12 or cols[0] != "5":
            continue
        text = cols[11].strip()
        try:
            conf = float(cols[10])
            left, top, w, h = (int(v) for v in cols[6:10])
        except ValueError:
            continue
        if conf < 0 or not text:
            continue
        lines.setdefault(tuple(cols[1:5]), []).append((left, top, w, h, conf, text))

    out = []
    for words in lines.values():
        text = " ".join(t for *_, t in words)
        if not any(c.isalnum() for c in text):
            continue
        confidence = sum(c for *_, c, _ in words) / len(words) / 100
        if confidence < min_confidence:
            continue
        x0 = min(w[0] for w in words)
        y0 = min(w[1] for w in words)
        x1 = max(w[0] + w[2] for w in words)
        y1 = max(w[1] + w[3] for w in words)
        x, y = max(x0 / width, 0.0), max(y0 / height, 0.0)
        out.append(
            OcrLine(
                text=text,
                confidence=round(min(max(confidence, 0.0), 1.0), 4),
                x=round(x, 5),
                y=round(y, 5),
                w=round(max(min(x1 / width, 1.0) - x, 1e-5), 5),
                h=round(max(min(y1 / height, 1.0) - y, 1e-5), 5),
            )
        )
    out.sort(key=lambda line: (line.y, line.x))
    return out


def read_text(image: Path, settings: Settings) -> list[OcrLine]:
    """OCR one image. Raises OcrError if Tesseract fails or times out."""
    work = Path(tempfile.mkdtemp(prefix="seehere-ocr-"))
    try:
        with Image.open(image) as im:
            gray = im.convert("L")
        if gray.width < UPSCALE_BELOW_WIDTH:
            gray = gray.resize((gray.width * 2, gray.height * 2), Image.Resampling.LANCZOS)
        png = work / "page.png"
        gray.save(png)
        try:
            result = subprocess.run(  # noqa: S603 - fixed argv, no shell
                [settings.tesseract_bin, str(png), "stdout", "-l", settings.ocr_language]
                + ["--psm", "3", "tsv"],
                capture_output=True,
                text=True,
                timeout=settings.ocr_timeout_s,
                env={**os.environ, "OMP_THREAD_LIMIT": "1"},
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise OcrError("tesseract timed out") from exc
        except OSError as exc:
            raise OcrError(f"tesseract could not run: {exc}") from exc
        if result.returncode != 0:
            raise OcrError(f"tesseract exited with {result.returncode}: {result.stderr[-300:]}")
        return parse_tsv(result.stdout, gray.width, gray.height, settings.ocr_min_confidence)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def queue_ocr(session: Session, project_id: uuid.UUID) -> None:
    """Queue (or re-queue) OCR after keyframes were chosen. Does not commit."""
    queue.enqueue_or_restart(
        session, project_id=project_id, kind=JOB_KIND, idempotency_key=f"{JOB_KIND}:{project_id}"
    )


def extract_text(ctx: JobContext, job: ClaimedJob) -> None:
    with ctx.session() as s:
        frame_ids = select(Frame.id).join(MediaAsset, Frame.media_asset_id == MediaAsset.id)
        frame_ids = frame_ids.where(
            MediaAsset.project_id == job.project_id, MediaAsset.kind == MediaKind.SOURCE_VIDEO
        )
        keyframes = list(
            s.execute(
                select(Frame.id, Frame.storage_path)
                .where(Frame.id.in_(frame_ids), Frame.is_keyframe.is_(True))
                .order_by(Frame.t_s)
            )
        )
    if not keyframes:
        raise PermanentJobError("No keyframes were found. Run scene detection again.")

    results: list[tuple[uuid.UUID, list[OcrLine]]] = []
    for n, (frame_id, rel) in enumerate(keyframes):
        ctx.progress("read", n / len(keyframes))
        try:
            results.append((frame_id, read_text(ctx.store.resolve(rel), ctx.settings)))
        except OcrError as exc:
            log.warning("OCR failed on frame %s: %s", frame_id, exc)
            raise RetryableJobError("Text recognition failed on a keyframe.") from exc
        except OSError as exc:
            raise PermanentJobError("A keyframe image could not be read.") from exc

    ctx.progress("save", 0.95)
    ctx.check_cancelled()
    with ctx.session() as s:
        s.execute(delete(OcrRegion).where(OcrRegion.frame_id.in_(frame_ids)))
        s.add_all(
            OcrRegion(
                frame_id=frame_id,
                text=line.text,
                confidence=line.confidence,
                x=line.x,
                y=line.y,
                w=line.w,
                h=line.h,
            )
            for frame_id, lines in results
            for line in lines
        )
        if has_deck(s, job.project_id):  # keyframe text changed: realign the deck
            queue_deck_ingest(s, job.project_id)
        queue_visual_analysis(s, job.project_id)
        s.commit()
    log.info(
        "project %s: %d text lines on %d keyframes",
        job.project_id,
        sum(len(lines) for _, lines in results),
        len(results),
    )
    ctx.progress("save", 1.0)
