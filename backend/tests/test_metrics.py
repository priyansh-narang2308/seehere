"""Job measurements, provider-call metering and the metrics API (Task 33)."""

from __future__ import annotations

import io
import subprocess
import uuid
import wave
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from seehere.api.main import app
from seehere.core.config import Settings, get_settings
from seehere.core.usage import measure, record_call
from seehere.db.models import Job, Project
from seehere.db.session import get_db
from seehere.jobs import metrics, queue
from seehere.jobs.errors import PermanentJobError
from seehere.jobs.queue import ClaimedJob
from seehere.jobs.worker import JobContext, Worker
from seehere.providers.stt_vultr import VultrWhisperSTT
from seehere.providers.tts_vultr import VultrTTS
from seehere.providers.vision_vultr import VultrVisionAnalyzer

Sessions = sessionmaker[Session]
KEY = "sk-metrics-test-key"


def _wav_bytes(seconds: float = 1.0, rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\0\0" * int(seconds * rate))
    return buf.getvalue()


# --- measuring ---------------------------------------------------------------------------------


def test_measure_counts_time_cpu_and_subprocess_cpu() -> None:
    with measure() as m:
        sum(i * i for i in range(200_000))
        subprocess.run(["python3", "-c", "sum(i for i in range(2_000_000))"], check=True)
    assert m.run_s > 0 and m.cpu_s > 0 and m.child_cpu_s > 0
    assert m.peak_rss_mb > 1 and m.child_peak_rss_mb > 1
    assert m.provider_calls == []


def test_calls_outside_a_measurement_are_ignored() -> None:
    record_call("tts", 200, 0.0, {"input_chars": 5})  # no error, nothing kept
    with measure() as m:
        pass
    assert m.provider_calls == []


def test_each_vultr_provider_records_its_calls_without_content(tmp_path: Path) -> None:
    def tts_reply(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=_wav_bytes(0.5))

    def stt_reply(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "no"})

    def vision_reply(_: httpx.Request) -> httpx.Response:
        body = {
            "choices": [{"message": {"content": '{"ok": true}'}}],
            "usage": {"prompt_tokens": 812, "completion_tokens": 40, "total_tokens": 852},
        }
        return httpx.Response(200, json=body)

    audio = tmp_path / "talk.wav"
    audio.write_bytes(_wav_bytes(2.0))
    image = tmp_path / "slide.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * 16)
    schema = {
        "type": "object",
        "properties": {"ok": {"type": "boolean"}},
        "required": ["ok"],
        "additionalProperties": False,
    }
    with measure() as m:
        VultrTTS(SecretStr(KEY), transport=httpx.MockTransport(tts_reply)).synthesize(
            "Hello there", tmp_path / "cue.wav"
        )
        with pytest.raises(Exception, match="401"):
            VultrWhisperSTT(SecretStr(KEY), transport=httpx.MockTransport(stt_reply)).transcribe(
                audio
            )
        VultrVisionAnalyzer(SecretStr(KEY), transport=httpx.MockTransport(vision_reply)).analyze(
            image, "describe", schema
        )
    tts, stt, vision = m.provider_calls
    assert (tts.operation, tts.status, tts.units) == ("tts", 200, {"input_chars": 11})
    assert (stt.operation, stt.status) == ("stt", 401)
    assert stt.units["audio_s"] == pytest.approx(2.0)
    assert vision.units == {"prompt_tokens": 812, "completion_tokens": 40}
    assert all(c.duration_ms >= 0 and c.service == "vultr" for c in m.provider_calls)
    assert KEY not in repr(m.as_json()) and "Hello there" not in repr(m.as_json())


# --- worker -------------------------------------------------------------------------------------


@pytest.fixture
def project_id(sessions: Sessions) -> uuid.UUID:
    with sessions() as s:
        p = Project(title="Lecture", rights_confirmed_at=datetime.now(UTC))
        s.add(p)
        s.commit()
        return p.id


def _enqueue(sessions: Sessions, pid: uuid.UUID, kind: str) -> uuid.UUID:
    with sessions() as s:
        job = queue.enqueue(s, project_id=pid, kind=kind, idempotency_key=f"{kind}:{uuid.uuid4()}")
        s.commit()
        return job.id


def test_worker_stores_one_measurement_per_attempt(
    sessions: Sessions, project_id: uuid.UUID, tmp_path: Path
) -> None:
    def ok(ctx: JobContext, job: ClaimedJob) -> None:
        record_call("tts", 200, 0.0, {"input_chars": 30})

    def broken(ctx: JobContext, job: ClaimedJob) -> None:
        record_call("tts", 401, 0.0, {"input_chars": 30})
        raise PermanentJobError("Vultr text-to-speech rejected the API key.")

    settings = Settings(media_dir=tmp_path / "media", job_heartbeat_interval_s=0.1)
    good = _enqueue(sessions, project_id, "test.ok")
    bad = _enqueue(sessions, project_id, "test.broken")
    worker = Worker({"test.ok": ok, "test.broken": broken}, settings=settings, sessions=sessions)
    while worker.run_once():
        pass
    with sessions() as s:
        jobs = {j.id: j for j in s.scalars(select(Job).where(Job.project_id == project_id))}
    [ok_attempt] = jobs[good].metrics
    [bad_attempt] = jobs[bad].metrics
    assert ok_attempt["outcome"] == "succeeded" and bad_attempt["outcome"] == "failed"
    assert ok_attempt["attempt"] == 1 and ok_attempt["run_s"] >= 0
    assert ok_attempt["provider_calls"][0]["units"] == {"input_chars": 30}

    with sessions() as s:
        report = metrics.project_metrics(s, settings, project_id)
        overall = metrics.summary(s, settings)
    assert [st["kind"] for st in report["stages"]] == ["test.ok", "test.broken"]
    [tts] = report["providers"]
    assert (tts["calls"], tts["failed"], tts["estimated_cost_usd"]) == (2, 1, None)
    assert report["prices_configured"] is False
    assert {st["kind"] for st in overall["stages"]} >= {"test.ok", "test.broken"}


# --- spend --------------------------------------------------------------------------------------


def _attempt(*calls: tuple[str, int | None, dict[str, float]]) -> dict[str, Any]:
    return {
        "provider_calls": [
            {"service": "vultr", "operation": op, "status": st, "duration_ms": 100, "units": u}
            for op, st, u in calls
        ]
    }


def test_spend_bills_only_successful_calls_at_configured_prices() -> None:
    priced = Settings(
        vultr_price_per_million_tokens_usd=2.0,
        vultr_price_per_million_tts_chars_usd=20.0,
        vultr_price_per_stt_minute_usd=0.006,
    )
    attempts = [
        _attempt(
            ("vision", 200, {"prompt_tokens": 400_000, "completion_tokens": 100_000}),
            ("tts", 200, {"input_chars": 50_000}),
            ("tts", 503, {"input_chars": 50_000}),
        ),
        _attempt(("stt", 200, {"audio_s": 600.0, "audio_bytes": 1.0})),
    ]
    rows = {r["operation"]: r for r in metrics.provider_spend(priced, attempts)}
    assert list(rows) == ["vision", "tts", "stt"]
    assert rows["vision"]["estimated_cost_usd"] == pytest.approx(1.0)
    assert rows["tts"]["estimated_cost_usd"] == pytest.approx(1.0)  # the 503 is not billed
    assert (rows["tts"]["calls"], rows["tts"]["failed"]) == (2, 1)
    assert rows["tts"]["units"] == {"input_chars": 100_000}
    assert rows["stt"]["estimated_cost_usd"] == pytest.approx(0.06)
    unpriced = metrics.provider_spend(Settings(), attempts)
    assert all(r["estimated_cost_usd"] is None for r in unpriced)


def test_percentile_is_nearest_rank() -> None:
    values = [float(v) for v in range(1, 21)]
    assert metrics._percentile(values, 50) == 10
    assert metrics._percentile(values, 95) == 19
    assert metrics._percentile([3.0], 95) == 3


# --- API ----------------------------------------------------------------------------------------


@pytest.fixture
def client(db: Session, tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(media_dir=tmp_path / "media")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_metrics_endpoints(client: TestClient, db: Session) -> None:
    p = Project(title="Lecture", rights_confirmed_at=datetime.now(UTC))
    db.add(p)
    db.flush()
    db.add(
        Job(
            project_id=p.id,
            kind="speech.synthesize",
            idempotency_key=f"k:{uuid.uuid4()}",
            metrics=[{"attempt": 1, "outcome": "succeeded", "run_s": 1.5, "cpu_s": 0.4}],
        )
    )
    db.flush()
    r = client.get(f"/api/projects/{p.id}/metrics")
    assert r.status_code == 200
    body = r.json()
    assert body["processing_s"] == 1.5 and body["stages"][0]["kind"] == "speech.synthesize"
    assert body["video_duration_s"] is None and body["processing_per_video_s"] is None
    summary = client.get("/api/metrics").json()
    assert any(st["kind"] == "speech.synthesize" for st in summary["stages"])
    assert client.get(f"/api/projects/{uuid.uuid4()}/metrics").status_code == 404
