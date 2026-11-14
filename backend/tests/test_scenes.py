"""Scene and slide change detection, checked against a synthetic lecture with known changes.

The demo clip (34 s, with per-frame noise and H.264 compression on top) is:

    0-6   slide A (title)
    6-12  slide B (two lines)                      cut
    12-16 slide B plus a third line                 bullet build (about 3% of the picture)
    16-18 crossfade B+ -> C                         2 s transition
    18-24 slide C (bar chart)
    24-28 slide A again                             revisit: must not become a new keyframe
    28-34 slide D

Ground truth: keyframes at 0, 6, 12, 18, 28 s and a revisit of A at 24 s.
"""

from __future__ import annotations

import shutil
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from seehere.core.config import Settings
from seehere.db.enums import JobStatus, MediaKind
from seehere.db.models import Frame, Job, MediaAsset, Project
from seehere.jobs.worker import Worker
from seehere.media import normalize, scenes
from seehere.media.scenes import changed_fraction, detect_scenes, dhash
from seehere.media.storage import MediaStore, source_video_path
from seehere.pipeline import HANDLERS, start_pipeline

Sessions = sessionmaker[Session]

BOX = "drawbox=x={}:y={}:w={}:h={}:color=black:t=fill"
SLIDE_A = [BOX.format(120, 140, 400, 70)]
SLIDE_B = [BOX.format(60, 60, 520, 24), BOX.format(60, 110, 480, 24)]
SLIDE_B2 = [*SLIDE_B, BOX.format(60, 160, 420, 24)]
SLIDE_C = [
    BOX.format(x, 300 - h, 60, h) for x, h in [(120, 80), (220, 160), (320, 120), (420, 220)]
]
SLIDE_D = [BOX.format(40, 40, 560, 280).replace("black", "navy")]

EXPECTED_KEYFRAMES = [0.0, 6.0, 12.0, 18.0, 28.0]
EXPECTED_REVISIT = 24.0


def _slide(boxes: list[str], seconds: int) -> list[str]:
    return ["-f", "lavfi", "-i", ",".join([f"color=c=white:s=640x360:r=10:d={seconds}", *boxes])]


@pytest.fixture(scope="module")
def lecture(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("scenes") / "slides.mp4"
    inputs = [
        *_slide(SLIDE_A, 6),
        *_slide(SLIDE_B, 6),
        *_slide(SLIDE_B2, 6),
        *_slide(SLIDE_C, 8),
        *_slide(SLIDE_A, 4),
        *_slide(SLIDE_D, 6),
        *["-f", "lavfi", "-i", "sine=duration=34"],
    ]
    graph = (
        # xfade needs both inputs on the same time base, so normalize it after concat.
        "[0][1][2]concat=n=3,settb=AVTB,fps=10[ab];[3]settb=AVTB,fps=10[c];"
        "[ab][c]xfade=transition=fade:duration=2:offset=16[abc];"
        "[abc][4][5]concat=n=3,noise=alls=8:allf=t,format=yuv420p[v]"
    )
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", graph, "-map", "[v]"]
        + ["-map", "6:a", "-c:v", "libx264", "-c:a", "aac", "-shortest", str(out)],
        check=True,
        capture_output=True,
        timeout=120,
    )
    return out


def _project(sessions: Sessions, settings: Settings, video: Path) -> uuid.UUID:
    with sessions() as s:
        project = Project(title="Slides", rights_confirmed_at=datetime.now(UTC))
        s.add(project)
        s.flush()
        rel = source_video_path(project.id, ".mp4")
        media = MediaAsset(
            project_id=project.id,
            kind=MediaKind.SOURCE_VIDEO,
            original_filename="slides.mp4",
            storage_path=rel,
            mime_type="video/mp4",
            size_bytes=video.stat().st_size,
            sha256="0" * 64,
        )
        s.add(media)
        s.flush()
        dest = MediaStore(settings.media_dir).resolve(rel)
        dest.parent.mkdir(parents=True)
        shutil.copyfile(video, dest)
        start_pipeline(s, project.id, media.id)
        s.commit()
        return project.id


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(media_dir=tmp_path / "media", job_heartbeat_interval_s=0.2)


def _run(sessions: Sessions, settings: Settings) -> None:
    kinds = (normalize.JOB_KIND, scenes.JOB_KIND)
    worker = Worker({k: HANDLERS[k] for k in kinds}, settings=settings, sessions=sessions)
    while worker.run_once():
        pass


def _frames(sessions: Sessions, pid: uuid.UUID) -> list[Frame]:
    with sessions() as s:
        return list(
            s.scalars(
                select(Frame)
                .join(MediaAsset, Frame.media_asset_id == MediaAsset.id)
                .where(MediaAsset.project_id == pid)
                .order_by(Frame.t_s)
            )
        )


def test_finds_every_slide_change_and_nothing_else(
    sessions: Sessions, settings: Settings, lecture: Path
) -> None:
    pid = _project(sessions, settings, lecture)
    _run(sessions, settings)
    with sessions() as s:
        job = s.scalars(select(Job).where(Job.project_id == pid, Job.kind == scenes.JOB_KIND)).one()
        assert (job.status, job.error) == (JobStatus.SUCCEEDED, None)

    frames = _frames(sessions, pid)
    assert len(frames) == 34
    keyframes = [f.t_s for f in frames if f.is_keyframe]
    # Precision and recall are both 1.0 on this clip: exactly the five slide changes.
    assert keyframes == EXPECTED_KEYFRAMES

    by_time = {f.t_s: f.scene_index for f in frames}
    assert by_time[EXPECTED_REVISIT] == by_time[0.0]  # slide A again, deduplicated
    assert len({f.scene_index for f in frames}) == 5
    # Frames inside each slide keep its scene; the crossfade frame stays with the old slide.
    for start, end in [(0, 6), (6, 12), (12, 18), (18, 24), (24, 28), (28, 34)]:
        assert {by_time[float(t)] for t in range(start, end)} == {by_time[float(start)]}, start
    assert all(f.phash and len(f.phash) == 16 for f in frames)


def test_running_again_gives_the_same_result(
    sessions: Sessions, settings: Settings, lecture: Path
) -> None:
    pid = _project(sessions, settings, lecture)
    _run(sessions, settings)
    first = [(f.t_s, f.is_keyframe, f.scene_index, f.phash) for f in _frames(sessions, pid)]
    with sessions() as s:
        job = s.scalars(select(Job).where(Job.project_id == pid, Job.kind == scenes.JOB_KIND)).one()
        job.status = JobStatus.FAILED
        s.commit()
        from seehere.jobs import queue

        queue.retry(s, job.id)
    _run(sessions, settings)
    assert [(f.t_s, f.is_keyframe, f.scene_index, f.phash) for f in _frames(sessions, pid)] == first


def _noisy(base: int, rng: np.random.Generator) -> np.ndarray:
    return np.clip(base + rng.normal(0, 6, (36, 64)), 0, 255).astype(np.int16)


def test_noise_alone_is_not_a_change() -> None:
    rng = np.random.default_rng(1)
    thumbs = [_noisy(200, rng) for _ in range(30)]
    r = detect_scenes(thumbs, fraction=0.02, pixel_delta=24)
    assert (r.keyframes, r.revisits, set(r.scene_index)) == ([0], [], {0})


def test_gradual_drift_is_caught_against_the_last_keyframe() -> None:
    # Brightness creeps up 6 levels per frame: no neighbour differs, but the total does.
    thumbs = [np.full((36, 64), 100 + 6 * i, dtype=np.int16) for i in range(10)]
    r = detect_scenes(thumbs, fraction=0.02, pixel_delta=24)
    assert r.keyframes == [0, 5]


def test_a_changing_picture_waits_until_it_settles() -> None:
    a, b = np.zeros((36, 64), np.int16), np.full((36, 64), 255, np.int16)
    mid = np.full((36, 64), 128, np.int16)
    r = detect_scenes([a, a, mid, b, b], fraction=0.02, pixel_delta=24)
    assert r.keyframes == [0, 3]  # not the half-faded frame
    assert r.scene_index == [0, 0, 0, 1, 1]


def test_empty_and_helpers() -> None:
    assert detect_scenes([], fraction=0.02, pixel_delta=24).keyframes == []
    a = np.zeros((36, 64), np.int16)
    b = a.copy()
    b[:18] = 255
    assert changed_fraction(a, b, 24) == 0.5
    ramp = np.tile(np.arange(64, dtype=np.int16) * 4, (36, 1))  # brighter to the right
    assert (dhash(a), dhash(ramp)) == ("0" * 16, "f" * 16)


def test_keyframes_are_served(sessions: Sessions, settings: Settings, lecture: Path) -> None:
    from fastapi.testclient import TestClient

    from seehere.api.main import app
    from seehere.core.config import get_settings
    from seehere.db.session import get_db

    pid = _project(sessions, settings, lecture)

    def db():  # type: ignore[no-untyped-def]
        with sessions() as s:
            yield s

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_db] = db
    try:
        with TestClient(app) as client:
            assert client.get(f"/api/projects/{pid}/media").json()["scenes"] is None
            _run(sessions, settings)
            scenes_out = client.get(f"/api/projects/{pid}/media").json()["scenes"]
    finally:
        app.dependency_overrides.clear()
    assert [k["t_s"] for k in scenes_out["keyframes"]] == EXPECTED_KEYFRAMES
    assert [k["scene_index"] for k in scenes_out["keyframes"]] == [0, 1, 2, 3, 4]
    assert scenes_out["revisits"] == 1
