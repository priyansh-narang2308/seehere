"""Export documents and the timing rule, as pure functions; plus real ffmpeg renders of both
described videos from a generated clip."""

from __future__ import annotations

import json
import shutil
import subprocess
import wave
from pathlib import Path

import pytest

from seehere.db.enums import VerificationState
from seehere.export.documents import (
    Voiced,
    extended_filter,
    mix_filter,
    pauses,
    to_extended,
    transcript_html,
    vtt_time,
    webvtt,
)
from seehere.schedule.timing import misfit

V = VerificationState.VERIFIED_TEXT_MATCH
A = Voiced("a", "On screen: “Next steps”.", 2.0, 1.5, 0.0, "audio/01-a.wav", V)
B = Voiced(
    "b", "Chart: Revenue --> up.", 5.0, 2.0, 1.2, "audio/02-b.wav", VerificationState.UNCERTAIN
)


def test_timing_rule() -> None:
    assert misfit(1.84, 1.84) is None and misfit(1.84, 1.8405) is None  # within 1 ms
    assert misfit(1.84, 2.21) == "its spoken audio (2.21 s) is longer than its slot (1.84 s)"
    assert misfit(1.84, None) == "no audio was generated for it"


def test_pauses_and_extended_time() -> None:
    assert B.pause_at_s == 5.8  # 0.8 s over silence, then the video holds 1.2 s
    holds = pauses([A, B])
    assert holds == [(5.8, 1.2)]
    assert to_extended(5.0, holds, after_pause_at_t=False) == 5.0
    assert to_extended(5.8, holds, after_pause_at_t=False) == 5.8
    assert to_extended(5.8, holds, after_pause_at_t=True) == 7.0
    assert to_extended(9.0, holds, after_pause_at_t=False) == 10.2


def test_webvtt_standard_and_extended() -> None:
    assert vtt_time(3725.5) == "01:02:05.500"
    std = webvtt([B, A], extended=False)
    assert std.splitlines()[:6] == [
        "WEBVTT",
        "Kind: descriptions",
        "Language: en",
        "",
        "d1",
        "00:00:02.000 --> 00:00:03.500",
    ]
    assert "Chart: Revenue → up." in std  # "-->" would end the cue timing line
    late = Voiced("c", "Later.", 9.0, 1.0, 0.0, "audio/03-c.wav", V)
    ext = webvtt([A, B, late], extended=True)
    assert "00:00:10.200 --> 00:00:11.200" in ext  # after the 1.2 s hold


def test_transcript_is_escaped_ordered_and_lists_what_was_not_voiced() -> None:
    page = transcript_html(
        "Week <1>",
        [(0.0, 1.9, "Hello & welcome."), (3.0, 4.0, "Next.")],
        [A],
        [(0.5, "On screen: “Quarterly”.", "no pause in speech while it is on screen")],
    )
    assert '<html lang="en">' in page and "<title>Week &lt;1&gt;: transcript" in page
    order = [page.index(s) for s in ("Hello &amp; welcome.", "Next steps", "Next.")]
    assert order == sorted(order)
    assert "(verified text match)" in page
    assert "not voiced: no pause in speech while it is on screen" in page


def test_filter_graphs() -> None:
    graph = mix_filter([A], 1, duck=0.3)
    assert "volume=0.3:enable='between(t,2.000,3.500)'" in graph
    assert "[1:a]aresample=48000,adelay=2000:all=1[d0]" in graph
    assert mix_filter([], 1, duck=0.3) == "[base]anull[aout]"
    graph, total = extended_filter([A, B], 10.0, 1)
    assert total == 11.2
    assert (
        "trim=start=0.000:end=5.800" in graph
        and "tpad=stop_mode=clone:stop_duration=1.200" in graph
    )
    assert "concat=n=2:v=1:a=1" in graph


def _tone_video(path: Path) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=320x240:rate=10",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=300",
            "-t",
            "6",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(path),
        ],
        check=True,
    )


def _clip(path: Path, seconds: float) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        w.writeframes(b"\x10\x00" * int(seconds * 22050))


def _probe(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(json.loads(out.stdout)["format"]["duration"])


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
@pytest.mark.parametrize("pause_at_start", [False, True])
def test_rendered_videos_have_the_planned_length(tmp_path: Path, pause_at_start: bool) -> None:
    video, clip = tmp_path / "v.mp4", tmp_path / "c.wav"
    _tone_video(video)
    _clip(clip, 1.5)
    start = 0.0 if pause_at_start else 2.0
    cue = Voiced("a", "x", start, 1.5, 1.0, str(clip), V)
    graph, total = extended_filter([cue], 6.0, 2)
    out = tmp_path / "ext.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-i",
            str(video),
            "-i",
            str(clip),
            "-filter_complex",
            f"[0:a]anull[base];{graph.replace('[2:a]', '[1:a]')}",
            "-map",
            "[vout]",
            "-map",
            "[aout]",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            str(out),
        ],
        check=True,
    )
    assert total == 7.0 and _probe(out) == pytest.approx(7.0, abs=0.15)
    std = tmp_path / "std.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-i",
            str(video),
            "-i",
            str(clip),
            "-filter_complex",
            f"[0:a]anull[base];{mix_filter([cue], 1, duck=0.3)}",
            "-map",
            "0:v",
            "-map",
            "[aout]",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            str(std),
        ],
        check=True,
    )
    assert _probe(std) == pytest.approx(6.0, abs=0.15)
