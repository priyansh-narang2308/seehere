"""Visual units: the Vultr vision adapter's schema checks and single retry, OCR text blocks,
and the visual.analyze job on a real rendered lecture video.

The adapter tests use httpx.MockTransport, so they say nothing about the live service. The live
test spends credit and runs only with the owner's approval:
    SEEHERE_LIVE_VULTR_VISION=1 VULTR_INFERENCE_API_KEY=... uv run pytest tests/test_vision.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx
import pytest
from pipeline_project import add_project, run_jobs
from pydantic import SecretStr
from slide_images import SLIDE_1, make_deck_video, render
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from seehere.core.config import Settings
from seehere.db.enums import VisualKind
from seehere.db.models import Frame, VisualUnit
from seehere.providers.base import Capability, VerificationState
from seehere.providers.vision_vultr import (
    VisionError,
    VisionOutputInvalid,
    VultrVisionAnalyzer,
    validate,
)
from seehere.vision import units as units_mod
from seehere.vision.schema import PROMPT, UNITS_SCHEMA
from seehere.vision.units import Box, appearances, group_text_blocks, units_from_model

Sessions = sessionmaker[Session]
KEY = "sk-test-not-a-real-key"
CHAIN = ("media.prepare", "scenes.detect", "ocr.extract", "visual.analyze")

CHART = {
    "kind": "chart",
    "label": "Bar chart of revenue by quarter",
    "details": "Four bars rising from Q1 to Q4.",
    "visible_text": ["Q1", "Q4", "$3.2M"],
    "box": {"x": 0.1, "y": 0.2, "w": 0.5, "h": 0.6},
}


def _reply(content: Any) -> httpx.Response:
    text = content if isinstance(content, str) else json.dumps(content)
    return httpx.Response(200, json={"choices": [{"message": {"content": text}}]})


def _analyzer(replies: list[httpx.Response], seen: list[dict[str, Any]]) -> VultrVisionAnalyzer:
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append({"auth": request.headers["authorization"], **json.loads(request.content)})
        return replies.pop(0)

    return VultrVisionAnalyzer(SecretStr(KEY), transport=httpx.MockTransport(handle))


@pytest.fixture
def image(tmp_path: Path) -> Path:
    render(SLIDE_1, tmp_path / "slide.png")
    return tmp_path / "slide.png"


# --- adapter ---


def test_valid_reply_is_returned_and_request_is_well_formed(image: Path) -> None:
    seen: list[dict[str, Any]] = []
    out = _analyzer([_reply({"units": [CHART]})], seen).analyze(image, PROMPT, UNITS_SCHEMA)
    assert out == {"units": [CHART]}
    (req,) = seen
    assert req["auth"] == f"Bearer {KEY}"
    assert req["response_format"]["json_schema"]["strict"] is True
    assert req["response_format"]["json_schema"]["schema"] == UNITS_SCHEMA
    parts = req["messages"][0]["content"]
    assert parts[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_invalid_reply_is_retried_once_with_the_reason(image: Path) -> None:
    seen: list[dict[str, Any]] = []
    bad = {"units": [{**CHART, "kind": "pie"}]}
    out = _analyzer([_reply(bad), _reply({"units": [CHART]})], seen).analyze(
        image, PROMPT, UNITS_SCHEMA
    )
    assert out["units"][0]["kind"] == "chart"
    assert len(seen) == 2
    correction = seen[1]["messages"][-1]["content"]
    assert "units/0/kind" in correction and "invalid" in correction


@pytest.mark.parametrize(
    "first,second",
    [
        ("not json", "{still not json"),
        ({"units": [{**CHART, "box": {"x": 0.1, "y": 0.2, "w": 1.5, "h": 0.1}}]}, {"units": "x"}),
        ({"units": [{**CHART, "extra": 1}]}, {}),
    ],
)
def test_invalid_twice_is_rejected(image: Path, first: Any, second: Any) -> None:
    seen: list[dict[str, Any]] = []
    with pytest.raises(VisionOutputInvalid, match="invalid output twice"):
        _analyzer([_reply(first), _reply(second)], seen).analyze(image, PROMPT, UNITS_SCHEMA)
    assert len(seen) == 2  # exactly one retry


def test_errors_never_leak_the_key(image: Path) -> None:
    for response in [httpx.Response(401, json={"error": KEY}), httpx.Response(200, text="<html>")]:
        with pytest.raises(VisionError) as exc:
            _analyzer([response], []).analyze(image, PROMPT, UNITS_SCHEMA)
        assert KEY not in str(exc.value)
    analyzer = _analyzer([], [])
    assert KEY not in repr(analyzer.__dict__)
    assert analyzer.info().capabilities == {
        Capability.VISION_STRUCTURED: VerificationState.DOCUMENTED
    }


def test_validate_reports_where_it_failed() -> None:
    with pytest.raises(ValueError, match="units/0/label"):
        validate(json.dumps({"units": [{**CHART, "label": ""}]}), UNITS_SCHEMA)


@pytest.mark.skipif(
    os.environ.get("SEEHERE_LIVE_VULTR_VISION") != "1",
    reason="live Vultr call spends credit; set SEEHERE_LIVE_VULTR_VISION=1 to run it",
)
def test_live_vultr_vision(image: Path) -> None:  # pragma: no cover - needs approval and a key
    settings = Settings()
    if settings.vultr_inference_api_key is None:
        pytest.fail(
            "VULTR_INFERENCE_API_KEY is empty: subscribe to Serverless Inference and add the key"
        )
    analyzer = VultrVisionAnalyzer(
        settings.vultr_inference_api_key,
        base_url=settings.vultr_inference_base_url,
        model=settings.vultr_vision_model,
    )
    out = analyzer.analyze(image, PROMPT, UNITS_SCHEMA)
    text = " ".join(t for u in out["units"] for t in u["visible_text"])
    assert "12.5%" in text


# --- units ---


def test_lines_group_into_blocks_by_vertical_gap() -> None:
    lines = [
        ("Second line of the paragraph", Box(0.1, 0.45, 0.5, 0.05)),
        ("Title", Box(0.1, 0.1, 0.3, 0.08)),
        ("First line of the paragraph", Box(0.1, 0.39, 0.5, 0.05)),
        ("Footer", Box(0.1, 0.9, 0.2, 0.04)),
    ]
    blocks = group_text_blocks(lines)
    assert [b.lines for b in blocks] == [
        ["Title"],
        ["First line of the paragraph", "Second line of the paragraph"],
        ["Footer"],
    ]
    para = blocks[1].box
    assert (para.x, para.y, para.w) == (0.1, 0.39, 0.5)
    assert para.h == pytest.approx(0.11)
    assert all(b.kind is VisualKind.TEXT_BLOCK and b.source == "ocr" for b in blocks)


def test_model_units_are_clipped_to_the_frame() -> None:
    reply = {"units": [{**CHART, "box": {"x": 0.8, "y": 0.5, "w": 0.5, "h": 0.4}}]}
    (u,) = units_from_model(reply, "vultr:test")
    assert u.kind is VisualKind.CHART and u.source == "vultr:test"
    assert (u.box.x, u.box.w) == (0.8, pytest.approx(0.2))
    assert u.values() == {"lines": CHART["visible_text"], "details": CHART["details"]}


# --- job ---


@pytest.fixture(scope="module")
def deck(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return make_deck_video(tmp_path_factory.mktemp("vision"))


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(media_dir=tmp_path / "media", job_heartbeat_interval_s=0.2)


def _units(sessions: Sessions, pid: object) -> list[tuple[float, float, VisualUnit]]:
    with sessions() as s:
        rows = s.execute(
            select(Frame.t_s, VisualUnit.t_end_s, VisualUnit)
            .join(Frame, VisualUnit.frame_id == Frame.id)
            .where(VisualUnit.project_id == pid)
            .order_by(VisualUnit.t_start_s, VisualUnit.y)
        )
        return [(t, end, u) for t, end, u in rows]


def test_job_builds_text_units_with_boxes_and_spans(
    sessions: Sessions, settings: Settings, deck: Path
) -> None:
    pid = add_project(sessions, settings, deck)
    run_jobs(sessions, settings, CHAIN)
    rows = _units(sessions, pid)
    spans = sorted({(u.t_start_s, u.t_end_s, kf) for kf, _, u in rows})
    # slide 1 is shown twice, so its units exist once per appearance
    assert spans == [(0.0, 5.0, 0.0), (5.0, 9.0, 5.0), (9.0, pytest.approx(12.0, abs=0.2), 0.0)]
    first = [u for _, _, u in rows if u.t_start_s == 0.0]
    assert [u.label for u in first] == [text for text, *_ in SLIDE_1]
    for u in first:
        assert u.kind is VisualKind.TEXT_BLOCK and u.source == "ocr"
        assert u.x is not None and u.w is not None and u.x >= 0 and u.x + u.w <= 1
        assert u.coverage_score is None  # no transcript yet


def test_model_units_replace_ocr_and_invalid_frames_keep_ocr(
    sessions: Sessions, settings: Settings, deck: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Keyframe 1 gets a valid chart; keyframe 2 is invalid twice and keeps its OCR blocks.
    replies = [_reply({"units": [CHART]}), _reply("x"), _reply("y")]
    analyzer = _analyzer(replies, [])
    monkeypatch.setattr(units_mod, "make_analyzer", lambda _settings: analyzer)
    pid = add_project(sessions, settings, deck)
    run_jobs(sessions, settings, CHAIN)
    by_time: dict[float, list[VisualUnit]] = {}
    for _, _, u in _units(sessions, pid):
        by_time.setdefault(u.t_start_s, []).append(u)
    assert [u.kind for u in by_time[0.0]] == [VisualKind.CHART]
    assert by_time[0.0][0].source.startswith("vultr:")
    assert by_time[0.0][0].values["details"] == CHART["details"]
    assert {u.source for u in by_time[5.0]} == {"ocr"}
    assert [u.kind for u in by_time[9.0]] == [VisualKind.CHART]  # slide 1's second appearance
    assert not replies


def test_appearances_split_revisits() -> None:
    frames = [(0.0, 0), (1.0, 0), (2.0, 1), (3.0, 0), (4.0, 2)]
    assert appearances(frames, 5.0) == {
        0: [(0.0, 2.0), (3.0, 4.0)],
        1: [(2.0, 3.0)],
        2: [(4.0, 5.0)],
    }


def test_vision_is_off_unless_enabled() -> None:
    assert units_mod.make_analyzer(Settings(vultr_inference_api_key=SecretStr(KEY))) is None
    on = Settings(vision_provider="vultr", vultr_inference_api_key=SecretStr(KEY))
    assert isinstance(units_mod.make_analyzer(on), VultrVisionAnalyzer)
    assert (
        units_mod.make_analyzer(Settings(vision_provider="vultr", vultr_inference_api_key=None))
        is None
    )
