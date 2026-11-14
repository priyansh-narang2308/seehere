"""On-screen text: Tesseract on slides rendered with known text, positions and numbers.
No mocks: the real tesseract binary, the real worker and Postgres."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pipeline_project import add_project, run_jobs
from slide_images import SLIDE_1, SLIDE_2, make_deck_video, render
from slide_images import norm as _norm
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from seehere.api.main import app
from seehere.core.config import Settings, get_settings
from seehere.db.enums import JobStatus
from seehere.db.models import Job
from seehere.db.session import get_db
from seehere.media import normalize, ocr, scenes
from seehere.media.ocr import OcrError, OcrLine, parse_tsv, read_text
from seehere.text.numbers import extract_numbers

Sessions = sessionmaker[Session]
OCR_CHAIN = (normalize.JOB_KIND, scenes.JOB_KIND, ocr.JOB_KIND)


def _iou(a: tuple[float, ...], line: OcrLine) -> float:
    ax0, ay0, aw, ah = a
    bx0, by0 = line.x, line.y
    ix = max(0.0, min(ax0 + aw, bx0 + line.w) - max(ax0, bx0))
    iy = max(0.0, min(ay0 + ah, by0 + line.h) - max(ay0, by0))
    inter = ix * iy
    return inter / (aw * ah + line.w * line.h - inter)


@pytest.mark.parametrize("size", [(1280, 720), (640, 360)])  # 640 wide uses the 2x upscale
def test_reads_slide_text_with_boxes(tmp_path: Path, size: tuple[int, int]) -> None:
    truth = render(SLIDE_1, tmp_path / "s.png", size)
    lines = read_text(tmp_path / "s.png", Settings())
    assert [_norm(line.text) for line in lines] == [_norm(t) for t, *_ in SLIDE_1]
    for line, (text, *_) in zip(lines, SLIDE_1, strict=True):
        assert _iou(truth[text], line) > 0.6, (text, line)
        assert 0.6 < line.confidence <= 1
    numbers = [n.value for line in lines for n in extract_numbers(line.text)]
    assert numbers == [Decimal("12.5"), Decimal(3_200_000), Decimal("41.7"), Decimal(2022)]


def test_blank_image_has_no_text(tmp_path: Path) -> None:
    Image.new("RGB", (1280, 720), "white").save(tmp_path / "blank.png")
    assert read_text(tmp_path / "blank.png", Settings()) == []


def test_tesseract_failures_are_reported(tmp_path: Path) -> None:
    render(SLIDE_2, tmp_path / "s.png")
    with pytest.raises(OcrError, match="could not run"):
        read_text(tmp_path / "s.png", Settings(tesseract_bin="/nonexistent/tesseract"))
    with pytest.raises(OcrError, match="exited"):
        read_text(tmp_path / "s.png", Settings(ocr_language="no-such-language"))


def test_parse_tsv_groups_words_into_lines() -> None:
    header = "\t".join(
        [
            "level",
            "page_num",
            "block_num",
            "par_num",
            "line_num",
            "word_num",
            "left",
            "top",
            "width",
            "height",
            "conf",
            "text",
        ]
    )
    rows = [
        "1\t1\t0\t0\t0\t0\t0\t0\t1000\t500\t-1\t",
        "5\t1\t1\t1\t1\t1\t100\t50\t200\t40\t96\tHello",
        "5\t1\t1\t1\t1\t2\t320\t52\t180\t40\t90\tworld",
        "5\t1\t1\t1\t2\t1\t100\t300\t50\t40\t95\t—",  # punctuation only: dropped
        "5\t1\t2\t1\t1\t1\t600\t400\t100\t30\t12\tnoise",  # below min confidence
        "5\t1\t2\t1\t2\t1\t600\t450\t100\t30\t-1\t ",  # empty word
        "5\t1\t3\t1\t1\t1\t900\t480\t200\t40\t80\tedge",  # box runs past the image
    ]
    lines = parse_tsv("\n".join([header, *rows]), 1000, 500, min_confidence=0.3)
    assert [(line.text, line.confidence) for line in lines] == [
        ("Hello world", 0.93),
        ("edge", 0.8),
    ]
    hello = lines[0]
    assert (hello.x, hello.y, hello.w, hello.h) == (0.1, 0.1, 0.4, 0.084)
    assert lines[1].x + lines[1].w <= 1.0 and lines[1].y + lines[1].h <= 1.0


# --- end to end ---


@pytest.fixture(scope="module")
def deck(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return make_deck_video(tmp_path_factory.mktemp("deck"))


def _client_get(sessions: Sessions, settings: Settings, url: str) -> dict:
    def db():  # type: ignore[no-untyped-def]
        with sessions() as s:
            yield s

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_db] = db
    try:
        with TestClient(app) as client:
            r = client.get(url)
            assert r.status_code == 200, r.text
            return r.json()
    finally:
        app.dependency_overrides.clear()


def test_keyframe_text_end_to_end(sessions: Sessions, tmp_path: Path, deck: Path) -> None:
    settings = Settings(media_dir=tmp_path / "media", job_heartbeat_interval_s=0.2)
    pid = add_project(sessions, settings, deck)
    assert _client_get(sessions, settings, f"/api/projects/{pid}/ocr") == {
        "available": False,
        "keyframes": [],
    }
    run_jobs(sessions, settings, OCR_CHAIN)

    body = _client_get(sessions, settings, f"/api/projects/{pid}/ocr")
    assert body["available"] is True
    # Two keyframes: the revisit of slide 1 at 9 s is not read again.
    assert [k["t_s"] for k in body["keyframes"]] == [0.0, 5.0]
    texts = [[_norm(r["text"]) for r in k["regions"]] for k in body["keyframes"]]
    assert texts == [[_norm(t) for t, *_ in SLIDE_1], [_norm(t) for t, *_ in SLIDE_2]]
    region = body["keyframes"][0]["regions"][1]
    assert 0 < region["x"] < 0.1 and 0.3 < region["y"] < 0.4 and region["confidence"] > 0.6

    # Re-running replaces the regions instead of adding to them.
    with sessions() as s:
        job = s.scalars(select(Job).where(Job.project_id == pid, Job.kind == ocr.JOB_KIND)).one()
        job.status = JobStatus.FAILED
        s.commit()
        from seehere.jobs import queue

        queue.retry(s, job.id)
    run_jobs(sessions, settings, OCR_CHAIN)
    assert _client_get(sessions, settings, f"/api/projects/{pid}/ocr") == body


def test_missing_tesseract_is_retried_with_a_message(
    sessions: Sessions, tmp_path: Path, deck: Path
) -> None:
    settings = Settings(
        media_dir=tmp_path / "media",
        job_heartbeat_interval_s=0.2,
        tesseract_bin="/nonexistent/tesseract",
    )
    pid = add_project(sessions, settings, deck)
    run_jobs(sessions, settings, OCR_CHAIN)
    with sessions() as s:
        job = s.scalars(select(Job).where(Job.project_id == pid, Job.kind == ocr.JOB_KIND)).one()
    assert (job.status, job.attempts, job.error) == (
        JobStatus.QUEUED,
        1,
        "Text recognition failed on a keyframe.",
    )
