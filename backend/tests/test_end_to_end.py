"""End-to-end and failure testing (Task 31).

1. A narrated slide lecture goes through the real HTTP upload and every pipeline stage with real
   tools (ffmpeg, Whisper, Tesseract, OR-Tools, Piper), ending in downloadable exports.
2. A hosted voice that rejects its key stops the pipeline with a message saying what to fix,
   keeps every earlier result, and a retry after the fix completes the run.
3. A provider that is briefly down is retried with backoff instead of failing.
4. An export interrupted mid-render leaves the previous files in place and no temp files.
5. Malformed API calls are refused with clear errors and change nothing.
"""

from __future__ import annotations

import shutil
import subprocess
import uuid
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import quote

import httpx
import pytest
from fastapi.testclient import TestClient
from pipeline_project import add_project, run_jobs, say
from slide_images import SLIDE_1, SLIDE_2, make_deck_video, render
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from seehere.api.main import app
from seehere.core.config import Settings, get_settings
from seehere.db.models import ExportArtifact
from seehere.db.session import get_db
from seehere.export import build
from seehere.jobs import queue
from seehere.jobs.errors import JobCancelled
from seehere.jobs.worker import JobContext
from seehere.media.storage import MediaStore
from seehere.pipeline import HANDLERS
from seehere.providers.errors import ProviderError, job_error
from seehere.providers.tts_vultr import VultrTTS
from seehere.speech import synthesize

Sessions = sessionmaker[Session]
APP = {"X-SeeHere-Request": "1"}
SCRIPT = (
    "This quarter, revenue rose twelve point five percent. [[slnc 600]] "
    "Look at this number here, forty one point seven percent. [[slnc 4000]] "
    "Now, this line matters most."
)
SPEECH = (
    "this quarter revenue rose twelve point five percent "
    "look at this number here forty one point seven percent"
)
TTS_CHAIN = ("speech.synthesize", "timing.check", "schedule.plan", "export.build")


def _piper_ready(cfg: Settings) -> bool:
    voice = Path(cfg.piper_voice_dir).expanduser() / f"{cfg.piper_voice}.onnx"
    return shutil.which(cfg.piper_bin) is not None and voice.is_file()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    cfg = Settings(media_dir=tmp_path / "media", job_heartbeat_interval_s=0.2)
    if not _piper_ready(cfg):
        pytest.skip("the Piper voice is not installed (make tts-voice)")
    return cfg


@pytest.fixture
def client(sessions: Sessions, settings: Settings) -> Iterator[TestClient]:
    def db() -> Iterator[Session]:
        with sessions() as s:
            yield s

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_db] = db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(scope="module")
def narrated(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """20 s lecture: slide 1 for 10 s while the speaker talks, slide 2 for 10 s with pauses."""
    if not shutil.which("say"):
        pytest.skip("needs macOS `say` to record real speech")
    d = tmp_path_factory.mktemp("narrated")
    render(SLIDE_1, d / "1.png")
    render(SLIDE_2, d / "2.png")
    subprocess.run(["say", "-o", str(d / "speech.aiff"), SCRIPT], check=True, timeout=60)
    out = d / "lecture.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y"]
        + ["-loop", "1", "-framerate", "10", "-t", "10", "-i", str(d / "1.png")]
        + ["-loop", "1", "-framerate", "10", "-t", "10", "-i", str(d / "2.png")]
        + ["-i", str(d / "speech.aiff")]
        + ["-filter_complex", "[0][1]concat=n=2,format=yuv420p[v];[2]apad=whole_dur=20[a]"]
        + ["-map", "[v]", "-map", "[a]", "-t", "20", "-c:v", "libx264", "-c:a", "aac", str(out)],
        check=True,
        capture_output=True,
        timeout=120,
    )
    return out


@pytest.fixture(scope="module")
def deck(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return make_deck_video(tmp_path_factory.mktemp("deck"))


def _jobs(client: TestClient, pid: uuid.UUID | str) -> dict[str, dict]:
    return {j["kind"]: j for j in client.get(f"/api/projects/{pid}/jobs").json()["jobs"]}


def _scheduled(sessions: Sessions, settings: Settings, deck: Path) -> uuid.UUID:
    """A project processed up to a speech-safe schedule (speech written as STT would)."""
    pid = add_project(sessions, settings, deck)
    run_jobs(
        sessions, settings, ("media.prepare", "scenes.detect", "ocr.extract", "visual.analyze")
    )
    say(sessions, pid, [(0.5 + 0.3 * i, w) for i, w in enumerate(SPEECH.split())])
    run_jobs(
        sessions,
        settings,
        ("coverage.score", "references.resolve", "descriptions.generate", "claims.verify")
        + ("schedule.plan",),
    )
    return pid


# --- 1. the full flow ---------------------------------------------------------------------------


def test_upload_to_published_exports_over_http(
    client: TestClient, sessions: Sessions, settings: Settings, narrated: Path
) -> None:
    settings.local_stt_model = "base.en"  # same model family, faster on CI machines
    r = client.post(
        "/api/projects",
        content=narrated.read_bytes(),
        headers={
            "X-SeeHere-Request": "1",
            "X-SeeHere-Title": quote("Quarterly review"),
            "X-SeeHere-Filename": quote("lecture.mp4"),
            "X-SeeHere-Rights-Confirmed": "true",
        },
    )
    assert r.status_code == 201, r.text
    pid = r.json()["id"]

    run_jobs(sessions, settings, HANDLERS.keys())

    jobs = _jobs(client, pid)
    assert {k: j["status"] for k, j in jobs.items()} == {
        k: "succeeded"
        for k in HANDLERS
        if k != "deck.ingest"  # no deck was uploaded
    }
    project = client.get(f"/api/projects/{pid}").json()
    assert project["status"] == "ready"

    words = " ".join(
        s["text"] for s in client.get(f"/api/projects/{pid}/transcript").json()["segments"]
    )
    assert "this line matters most" in words.lower()
    cues = client.get(f"/api/projects/{pid}/cues").json()["cues"]
    assert any("Hire 3 engineers by March" in c["text_short"] for c in cues)

    plan = client.get(f"/api/projects/{pid}/schedule").json()
    assert plan["placements"], [n["reason"] for n in plan["not_placed"]]
    for p in plan["placements"]:  # voiced, measured and fitting its pause
        assert p["audio_s"] and p["audio_s"] <= p["end_s"] - p["start_s"] + 0.001

    files = {f["filename"]: f for f in client.get(f"/api/projects/{pid}/exports").json()["files"]}
    assert len(files) == 9
    vtt = client.get(files["descriptions.vtt"]["url"]).text
    assert vtt.count(" --> ") == len(plan["placements"])
    report = client.get(f"/api/projects/{pid}/report").json()
    assert report["summary"]["described"] == len({p["cue_id"] for p in plan["placements"]})
    assert (
        client.get(f"/api/projects/{pid}/video", headers={"Range": "bytes=0-9"}).status_code == 206
    )
    perf = client.get(f"/api/projects/{pid}/metrics").json()  # every stage was measured
    assert {st["kind"] for st in perf["stages"]} == set(jobs)
    assert all(st["run_s"] > 0 for st in perf["stages"])
    assert perf["video_duration_s"] == pytest.approx(20, abs=0.5)
    assert perf["processing_per_video_s"] > 0 and perf["providers"] == []  # all local


# --- 2-3. provider failures ---------------------------------------------------------------------


def _vultr_tts(status: int) -> VultrTTS:
    def reply(_: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"error": "nope"})

    from pydantic import SecretStr

    return VultrTTS(SecretStr("sk-secret-test-key"), transport=httpx.MockTransport(reply))


def test_rejected_key_stops_cleanly_and_retry_after_the_fix_completes(
    client: TestClient,
    sessions: Sessions,
    settings: Settings,
    deck: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pid = _scheduled(sessions, settings, deck)
    plan_before = client.get(f"/api/projects/{pid}/schedule").json()
    assert plan_before["placements"]

    monkeypatch.setattr(synthesize, "make_tts", lambda _cfg: _vultr_tts(401))
    run_jobs(sessions, settings, TTS_CHAIN)
    job = _jobs(client, pid)["speech.synthesize"]
    assert job["status"] == "failed" and job["attempts"] == 1  # not retried: it cannot pass
    assert "rejected the API key (HTTP 401)" in job["error"]
    assert "sk-secret" not in job["error"]
    assert "export.build" not in _jobs(client, pid)  # nothing half-built
    assert client.get(f"/api/projects/{pid}").json()["status"] == "failed"
    [tts] = client.get(f"/api/projects/{pid}/metrics").json()["providers"]
    assert (tts["operation"], tts["calls"], tts["failed"]) == ("tts", 1, 1)  # metered, unbilled
    # Earlier results stay available.
    assert (
        client.get(f"/api/projects/{pid}/schedule").json()["placements"]
        == plan_before["placements"]
    )

    monkeypatch.undo()  # the key is fixed (here: back to the local voice)
    r = client.post(f"/api/jobs/{job['id']}/retry", headers=APP)
    assert r.status_code == 200, r.text
    run_jobs(sessions, settings, TTS_CHAIN)
    jobs = _jobs(client, pid)
    assert all(jobs[k]["status"] == "succeeded" for k in TTS_CHAIN)
    assert client.get(f"/api/projects/{pid}").json()["status"] == "ready"
    assert len(client.get(f"/api/projects/{pid}/exports").json()["files"]) == 9


def test_provider_that_is_briefly_down_is_retried_with_backoff(
    client: TestClient,
    sessions: Sessions,
    settings: Settings,
    deck: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pid = _scheduled(sessions, settings, deck)
    monkeypatch.setattr(synthesize, "make_tts", lambda _cfg: _vultr_tts(503))
    run_jobs(sessions, settings, ("speech.synthesize",))
    job = _jobs(client, pid)["speech.synthesize"]
    assert job["status"] == "queued" and job["attempts"] == 1  # waits for its next attempt
    assert job["error"] == "Vultr text-to-speech is unavailable right now (HTTP 503)."
    assert job["run_after"] is not None


@pytest.mark.parametrize(
    ("status", "retryable", "kind", "text"),
    [
        (401, False, "Permanent", "rejected the API key"),
        (403, False, "Permanent", "rejected the API key"),
        (400, False, "Permanent", "refused the request (HTTP 400)"),
        (408, True, "Retryable", "unavailable right now (HTTP 408)"),
        (429, True, "Retryable", "unavailable right now (HTTP 429)"),
        (502, True, "Retryable", "unavailable right now (HTTP 502)"),
        (None, True, "Retryable", "unavailable right now (no response)"),
    ],
)
def test_provider_failures_map_to_the_right_job_outcome(
    status: int | None, retryable: bool, kind: str, text: str
) -> None:
    exc = ProviderError("boom", status=status)
    assert exc.retryable is retryable
    err = job_error(exc, "Service")
    assert type(err).__name__ == f"{kind}JobError" and text in err.message
    assert job_error(ProviderError("too big", retryable=False), "S").message == (
        "S refused the request: too big."
    )


# --- 4. interrupted export ----------------------------------------------------------------------


def test_export_interrupted_mid_render_keeps_the_previous_files(
    client: TestClient, sessions: Sessions, settings: Settings, deck: Path
) -> None:
    pid = _scheduled(sessions, settings, deck)
    run_jobs(sessions, settings, TTS_CHAIN)
    before = {
        f["filename"]: f["sha256"]
        for f in client.get(f"/api/projects/{pid}/exports").json()["files"]
    }
    assert len(before) == 9

    with sessions() as s:
        build.queue_export(s, pid)
        s.commit()
        claimed = queue.claim(s, "w", [build.JOB_KIND])
    assert claimed is not None
    ctx = JobContext(claimed, "w", settings, MediaStore(settings.media_dir), sessions)
    original = ctx.progress

    def cancel_while_rendering(stage: str, fraction: float) -> None:
        if stage == "render":
            ctx.cancel_event.set()
        original(stage, fraction)

    ctx.progress = cancel_while_rendering  # type: ignore[method-assign]
    with pytest.raises(JobCancelled):
        build.build_export(ctx, claimed)

    after = {
        f["filename"]: f["sha256"]
        for f in client.get(f"/api/projects/{pid}/exports").json()["files"]
    }
    assert after == before
    with sessions() as s:
        paths = s.scalars(
            select(ExportArtifact.storage_path).where(ExportArtifact.project_id == pid)
        )
        assert all(MediaStore(settings.media_dir).resolve(p).is_file() for p in paths)
    tmp = settings.media_dir / "tmp"
    assert not tmp.exists() or list(tmp.iterdir()) == []


# --- 5. malformed requests ----------------------------------------------------------------------


def test_malformed_requests_are_refused_and_change_nothing(
    client: TestClient, sessions: Sessions, settings: Settings, deck: Path
) -> None:
    pid = _scheduled(sessions, settings, deck)
    jobs_before = _jobs(client, pid)
    cue = client.get(f"/api/projects/{pid}/cues").json()["cues"][0]
    url = f"/api/cues/{cue['id']}/review"
    nobody = uuid.uuid4()
    cases = [
        (client.post(url, json={"action": "approve"}), 403),  # no app header (cross-site)
        (client.post(url, json={"action": "delete"}, headers=APP), 422),
        (client.post(url, json={"action": "edit", "text": "   "}, headers=APP), 422),
        (client.post(url, json={"action": "edit", "text": "x" * 2001}, headers=APP), 422),
        (
            client.post(
                url, content=b"{not json", headers=APP | {"Content-Type": "application/json"}
            ),
            422,
        ),
        (client.post(f"/api/cues/{nobody}/review", json={"action": "approve"}, headers=APP), 404),
        (client.get(f"/api/projects/{nobody}/report"), 404),
        (client.get(f"/api/projects/{pid}/schedule?mode=sideways"), 422),
        (client.get("/api/projects/not-a-uuid/cues"), 422),
        (client.get(f"/api/exports/{nobody}"), 404),
        (client.post(f"/api/jobs/{nobody}/retry", headers=APP), 404),
    ]
    for response, status in cases:
        assert response.status_code == status, (response.request.url, response.text)
        body = response.json()
        assert "Traceback" not in response.text
        assert body.get("error") or body.get("detail")
    after = client.get(f"/api/projects/{pid}/cues").json()["cues"][0]
    assert after == cue
    assert _jobs(client, pid) == jobs_before  # nothing queued, cancelled or retried


def test_ready_status_tracks_the_real_final_stage() -> None:
    assert queue.EXPORT_KIND == build.JOB_KIND
