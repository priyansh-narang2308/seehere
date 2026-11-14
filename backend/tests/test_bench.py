"""Benchmark (Task 30): annotation format, WebVTT import and metrics, without a database."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from seehere.bench.annotation import FORMAT, AnnotationError, load, parse
from seehere.bench.metrics import Said, conveys, score
from seehere.bench.runner import markdown, results
from seehere.bench.systems import OBSERVED, SystemRun, microsoft_system, parse_webvtt

REPO = Path(__file__).resolve().parents[2]


def _ann(**over: Any) -> dict[str, Any]:
    return {
        "format": FORMAT,
        "item": "t",
        "duration_s": 20.0,
        "speech": [[0.0, 5.0], [8.0, 12.0]],
        "visuals": [
            {
                "id": "a",
                "t_start_s": 0.0,
                "t_end_s": 10.0,
                "text": "Margin 41.7% in 2022",
                "facts": ["Margin", "2022"],
                "must_describe": True,
            },
            {
                "id": "b",
                "t_start_s": 10.0,
                "t_end_s": 20.0,
                "text": "Next steps",
                "facts": ["Next steps"],
                "must_describe": True,
            },
            {
                "id": "c",
                "t_start_s": 0.0,
                "t_end_s": 20.0,
                "text": "Logo",
                "facts": [],
                "must_describe": False,
            },
        ],
    } | over


def test_the_committed_annotation_is_valid() -> None:
    ann = load(REPO / "bench" / "annotations" / "pointers.json")
    assert ann.item == "pointers" and len(ann.source_sha256) == 64
    assert all(v.must_describe and v.facts for v in ann.visuals)


@pytest.mark.parametrize(
    ("over", "message"),
    [
        ({"format": "other"}, "format"),
        ({"speech": [[3.0, 2.0]]}, r"speech\[0\]"),
        ({"visuals": [{"id": "a", "t_start_s": 0, "t_end_s": 30}]}, "outside"),
        ({"visuals": [{"t_start_s": 0, "t_end_s": 1}]}, "unique id"),
        ({"duration_s": "15"}, "duration_s"),
    ],
)
def test_bad_annotations_are_refused(over: dict[str, Any], message: str) -> None:
    with pytest.raises(AnnotationError, match=message):
        parse(_ann(**over))


def test_facts_match_whole_words_ignoring_case_and_quotes() -> None:
    assert conveys("On screen: “Operating margin 41.7% in 2022”.", "operating margin")
    assert conveys("Revenue rose to $3.2M.", "$3.2M")
    assert not conveys("In 20220 they", "2022")
    assert not conveys("anything", "")


def test_metrics_count_recall_overlap_pauses_and_invented_numbers() -> None:
    ann = parse(_ann())
    said = [
        Said(5.2, 7.8, "On screen: “Margin 41.7% in 2022”."),  # in a pause: a, both facts
        Said(11.0, 14.0, "Next steps; revenue up 15%."),  # 1 s over speech, 15% not shown
        Said(15.0, 18.0, "Logo.", pause_s=2.0),  # extended: only 1 s heard
    ]
    m = score(ann, said)
    assert m["visual_recall"] == 1.0 and m["fact_recall"] == 1.0
    assert m["speech_overlap_s"] == 1.0
    assert m["paused_s"] == 2.0 and m["described_s"] == pytest.approx(2.6 + 3.0 + 1.0)
    assert m["unsupported_numbers"] == ["15%"]
    late = score(ann, [Said(13.0, 14.0, "Margin in 2022")])  # after a left the screen + grace
    assert late["visual_recall"] == 0.0 and late["per_visual"][0]["conveyed"] == []


def test_webvtt_from_the_baseline_is_read_as_timed_descriptions(tmp_path: Path) -> None:
    vtt = tmp_path / "out.vtt"
    vtt.write_text(
        "WEBVTT\n\nNOTE drafted\n\n1\n00:00:05.200 --> 00:00:07.800\n<v AD>A slide titled"
        "\nMargin 2022.</v>\n\n00:13.000 --> 00:14.500\nNext steps.\n",
        "utf-8",
    )
    cues = parse_webvtt(vtt.read_text("utf-8"))
    assert cues == [
        Said(5.2, 7.8, "A slide titled Margin 2022."),
        Said(13.0, 14.5, "Next steps."),
    ]
    run = microsoft_system(vtt)
    assert run.label == OBSERVED and len(run.said) == 2
    missing = microsoft_system(None)
    assert missing.label == "UNAVAILABLE" and "Azure" in missing.note


def test_unavailable_systems_report_no_numbers() -> None:
    ann = parse(_ann())
    res = results(ann, [microsoft_system(None), SystemRun("x", OBSERVED, [Said(5.2, 6, "Margin")])])
    assert res["systems"][0]["metrics"] is None
    table = markdown(res)
    assert "| microsoft-ai-audio-descriptions | UNAVAILABLE | – | – | – | – | – | – |" in table
    assert "| x | OBSERVED | 1 | 50% | 33% | 0.00 | 0.00 | none |" in table
    assert json.loads(json.dumps(res)) == res
