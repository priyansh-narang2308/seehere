"""Description cues and their evidence ledger, end to end on a rendered lecture video:
units -> seen versus said -> spoken references -> cues -> GET /api/cues/{id}/evidence."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pipeline_project import add_project, run_jobs, say
from slide_images import make_deck_video
from sqlalchemy.orm import Session, sessionmaker

from seehere.api.main import app
from seehere.core.config import Settings, get_settings
from seehere.db.enums import VisualKind
from seehere.db.session import get_db
from seehere.describe.generate import write_wordings
from seehere.text.numbers import extract_numbers

Sessions = sessionmaker[Session]
UNITS_CHAIN = ("media.prepare", "scenes.detect", "ocr.extract", "visual.analyze")
TEXT_CHAIN = ("coverage.score", "references.resolve", "descriptions.generate")


# --- wordings ---


def test_text_on_screen_is_quoted_as_read() -> None:
    w = write_wordings(VisualKind.TEXT_BLOCK, "Revenue rose 12.5%", ["Revenue rose 12.5%"], "")
    assert w == type(w)("On screen: “Revenue rose 12.5%”.", None, None)
    two = write_wordings(VisualKind.TEXT_BLOCK, "Next steps", ["Next steps", "Hire 3 by March"], "")
    assert two.short == "On screen: “Next steps”."
    assert two.medium == "On screen: “Next steps”. “Hire 3 by March”."
    assert two.long is None  # nothing more to say


def test_chart_wordings_grow_from_label_to_details_and_text() -> None:
    w = write_wordings(
        VisualKind.CHART,
        "Bar chart of revenue by quarter",
        ["Q1", "Q2", "Q3", "Q4", "$3.2M"],
        "Four bars rising from Q1 to Q4.",
    )
    assert w.short == "Chart: Bar chart of revenue by quarter."
    assert w.medium == f"{w.short} “Q1”. “Q2”."
    assert w.long == f"{w.short} Four bars rising from Q1 to Q4. “Q1”. “Q2”. “Q3”. “Q4”. “$3.2M”."


def test_long_lines_are_cut_at_a_word() -> None:
    line = " ".join(f"w{i}" for i in range(30))
    assert write_wordings(VisualKind.TEXT_BLOCK, line, [line], "").short.endswith("w14…”.")


# --- job and ledger ---


@pytest.fixture(scope="module")
def deck(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return make_deck_video(tmp_path_factory.mktemp("describe"))


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(media_dir=tmp_path / "media", job_heartbeat_interval_s=0.2)


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


SPEECH = (
    "this quarter revenue rose twelve point five percent "
    "look at this number here forty one point seven percent"
)


def test_cues_carry_their_full_evidence(
    client: TestClient, sessions: Sessions, settings: Settings, deck: Path
) -> None:
    pid = add_project(sessions, settings, deck)
    run_jobs(sessions, settings, UNITS_CHAIN)
    assert client.get(f"/api/projects/{pid}/cues").json() == {"available": False, "cues": []}
    say(sessions, pid, [(0.5 + 0.3 * i, w) for i, w in enumerate(SPEECH.split())])
    run_jobs(sessions, settings, TEXT_CHAIN)

    # "this number here" + "forty one point seven percent" -> the margin line
    refs = client.get(f"/api/projects/{pid}/references").json()["references"]
    assert [(r["phrase"], r["status"], r["label"]) for r in refs] == [
        ("this number here", "linked", "Operating margin 41.7% in 2022")
    ]

    body = client.get(f"/api/projects/{pid}/cues").json()
    cues = {c["text_short"]: c for c in body["cues"]}
    # slide 1's revisit is not described twice; every cue starts as needs review
    assert set(cues) == {
        "On screen: “Quarterly Revenue”.",
        "On screen: “Revenue rose 12.5% to $3.2M”.",
        "On screen: “Operating margin 41.7% in 2022”.",
        "On screen: “Next steps”.",
        "On screen: “Hire 3 engineers by March”.",
    }
    assert {c["verification_state"] for c in body["cues"]} == {"needs_review"}
    margin = cues["On screen: “Operating margin 41.7% in 2022”."]
    assert margin["anchor_t_s"] == pytest.approx(refs[0]["t_s"])  # anchored where it was pointed at
    assert cues["On screen: “Next steps”."]["anchor_t_s"] == 5.0

    ledger = client.get(f"/api/cues/{margin['id']}/evidence").json()
    kinds = [e["kind"] for e in ledger["evidence"]]
    assert kinds == ["frame", "ocr_region", "transcript_span", "transcript_span", "visual_unit"]
    by_kind = {e["kind"]: e for e in ledger["evidence"]}
    assert by_kind["frame"]["frame"]["t_s"] == 0.0
    assert client.get(by_kind["frame"]["frame"]["image_url"]).status_code == 200
    assert by_kind["ocr_region"]["ocr_region"]["text"] == "Operating margin 41.7% in 2022"
    spans = {e["note"]: e["transcript"]["text"] for e in ledger["evidence"] if e["transcript"]}
    assert spans["spoken reference: this number here"] == "this number here"
    assert spans["speech while shown"].startswith("this quarter revenue")
    unit = by_kind["visual_unit"]["visual_unit"]
    assert (unit["label"], unit["t_start_s"], unit["t_end_s"]) == (
        "Operating margin 41.7% in 2022",
        0.0,
        5.0,
    )
    assert ledger["checks"] == []  # claim verification is Task 17

    # No value in any wording that is not in the cue's own evidence.
    for c in body["cues"]:
        ev = client.get(f"/api/cues/{c['id']}/evidence").json()["evidence"]
        shown = " ".join(e["ocr_region"]["text"] for e in ev if e["ocr_region"])
        allowed = {n.raw for n in extract_numbers(shown)}
        for text in (c["text_short"], c["text_medium"], c["text_long"]):
            assert {n.raw for n in extract_numbers(text or "")} <= allowed

    assert client.get(f"/api/cues/{uuid.uuid4()}/evidence").status_code == 404
    assert client.get(f"/api/projects/{uuid.uuid4()}/cues").status_code == 404


def test_silent_lecture_still_gets_descriptions(
    client: TestClient, sessions: Sessions, settings: Settings, deck: Path
) -> None:
    pid = add_project(sessions, settings, deck)
    run_jobs(sessions, settings, ("speech.transcribe", *UNITS_CHAIN, *TEXT_CHAIN))
    body: dict[str, Any] = client.get(f"/api/projects/{pid}/cues").json()
    # The deck video's audio is a tone: no words, so everything on screen is unsaid.
    assert body["available"] and len(body["cues"]) == 5
    refs = client.get(f"/api/projects/{pid}/references").json()
    assert refs == {"available": True, "references": []}


def test_cues_are_verified_and_scheduled_into_speech_pauses(
    client: TestClient, sessions: Sessions, settings: Settings, deck: Path
) -> None:
    pid = add_project(sessions, settings, deck)
    run_jobs(sessions, settings, UNITS_CHAIN)
    assert client.get(f"/api/projects/{pid}/schedule").json()["available"] is False
    # 18 words of continuous speech from 0.5 to 5.9 s, then silence until the end (12 s).
    say(sessions, pid, [(0.5 + 0.3 * i, w) for i, w in enumerate(SPEECH.split())])
    run_jobs(sessions, settings, (*TEXT_CHAIN, "claims.verify", "schedule.plan"))

    cues = client.get(f"/api/projects/{pid}/cues").json()["cues"]
    # Every quote and number was read on screen, so each cue is a verified text match.
    assert {c["verification_state"] for c in cues} == {"verified_text_match"}
    ledger = client.get(f"/api/cues/{cues[0]['id']}/evidence").json()
    assert ledger["checks"] and {c["result"] for c in ledger["checks"]} == {"pass"}

    plan = client.get(f"/api/projects/{pid}/schedule").json()
    assert (plan["solver"], plan["mode"], plan["status"]) == ("cp_sat", "standard", "succeeded")
    cmp = plan["comparison"]  # both solvers ran on the same inputs; CP-SAT is never worse
    assert cmp["cp_sat"]["status"] == "optimal"
    assert cmp["cp_sat"]["priority_placed_share"] >= cmp["greedy"]["priority_placed_share"]
    assert plan["windows"] == [{"start_s": 6.05, "end_s": pytest.approx(12.0, abs=0.1)}]
    placed = plan["placements"]
    assert placed, plan
    for a, b in zip(placed, placed[1:], strict=False):
        assert a["end_s"] <= b["start_s"]  # never over each other
    for p in placed:  # never over speech
        assert 6.05 <= p["start_s"] < p["end_s"] <= plan["windows"][0]["end_s"]
    # Slide 1 (0-5 s, +1 s grace) is talked over the whole time: it cannot be voiced.
    reasons = {n["text"]: n["reason"] for n in plan["not_placed"]}
    assert reasons["On screen: “Quarterly Revenue”."] == "no pause in speech while it is on screen"
    assert {p["text"] for p in placed} <= {
        "On screen: “Next steps”.",
        "On screen: “Hire 3 engineers by March”.",
    }
    assert len(placed) + len(plan["not_placed"]) == len(cues)
    assert {p["text"] for p in placed} <= {c["text_short"] for c in cues} | {
        c["text_medium"] for c in cues
    } | {c["text_long"] for c in cues}

    ext = client.get(f"/api/projects/{pid}/schedule?mode=extended").json()
    assert (ext["mode"], ext["status"]) == ("extended", "succeeded")
    assert ext["pause_budget_s"] == pytest.approx(12.0 * 0.08, abs=0.05)
    assert 0 <= ext["paused_s"] <= ext["pause_budget_s"]
    standard = {(p["cue_id"], p["start_s"]) for p in placed}
    assert standard <= {(p["cue_id"], p["start_s"]) for p in ext["placements"]}
    for p in ext["placements"]:
        assert (p["pause_s"] > 0) == (p["pause_reason"] is not None)
    assert len(ext["placements"]) + len(ext["not_placed"]) == len(cues)

    # Speech synthesis: every wording a schedule uses gets real audio, measured from the file.
    run_jobs(sessions, settings, ("speech.synthesize",))
    voiced = client.get(f"/api/projects/{pid}/schedule?mode=extended").json()["placements"]
    for p in voiced:
        assert p["audio_s"] > 0.3
        wav = client.get(p["audio_url"])
        assert wav.status_code == 200 and wav.content[:4] == b"RIFF"

    # Timing check: re-solves with measured audio (at most 3 rounds), then the export is built.
    run_jobs(sessions, settings, ("speech.synthesize", "timing.check", "schedule.plan"))
    final = client.get(f"/api/projects/{pid}/schedule").json()
    for p in final["placements"]:  # every voiced description now fits its slot exactly
        assert p["audio_s"] is not None and p["audio_s"] <= p["end_s"] - p["start_s"] + 0.001
    run_jobs(sessions, settings, ("export.build",))
    files = {f["filename"]: f for f in client.get(f"/api/projects/{pid}/exports").json()["files"]}
    assert set(files) == {
        "descriptions.vtt",
        "cue-audio.zip",
        "lecture-described.mp4",
        "lecture-extended.mp4",
        "transcript.html",
        "manifest.json",
        "seehere-export.zip",
    }
    vtt = client.get(files["descriptions.vtt"]["url"])
    assert vtt.headers["content-disposition"].startswith("attachment")
    assert vtt.text.startswith("WEBVTT\nKind: descriptions")
    assert vtt.text.count(" --> ") == len(final["placements"])
    manifest = client.get(files["manifest.json"]["url"]).json()
    assert "not a WCAG conformance certification" in manifest["notice"]
    assert {d["cue_id"] for d in manifest["descriptions"] if d["mode"] == "standard"} == {
        p["cue_id"] for p in final["placements"]
    }
    assert all(d["evidence"] and d["checks"] for d in manifest["descriptions"])
    html = client.get(files["transcript.html"]["url"]).text
    assert '<html lang="en">' in html and "Description:" in html

    # The player streams the lecture with range requests, so it can seek.
    part = client.get(f"/api/projects/{pid}/video", headers={"Range": "bytes=0-99"})
    assert part.status_code == 206 and len(part.content) == 100
