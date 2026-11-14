"""Measure a real lecture going through the running app (Task 33).

    uv run python -m seehere.bench.perf make-lecture var/perf/lecture.mp4 --slides 8
    uv run python -m seehere.bench.perf run var/perf/lecture.mp4 --out ../bench/results

`make-lecture` builds a narrated slide lecture (macOS `say` for the voice, Pillow for slides,
ffmpeg to join them) so the measurement uses real speech, real OCR and real scheduling.
`run` uploads a video to the API, waits for the worker to finish every stage, then saves the
project's measured stage timings, resource use and provider calls as JSON and Markdown. Every
number in the output was observed on this machine during this run.
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

TOPICS = [
    ("Quarterly Revenue", ["Revenue rose 12.5% to $3.2M", "Operating margin 41.7% in 2022"]),
    ("Customer Growth", ["Active users reached 48,000", "Churn fell to 2.1% per month"]),
    ("Cost Breakdown", ["Cloud spend $410K per quarter", "Support costs down 18%"]),
    ("Hiring Plan", ["Hire 3 engineers by March", "Open 2 design roles in Q2"]),
    ("Product Roadmap", ["Launch mobile app in June", "Offline mode by September"]),
    ("Risks", ["Supplier delay of 6 weeks", "Currency exposure 14% of revenue"]),
    ("Market Share", ["Share grew from 9% to 13%", "Top region: Northern Europe"]),
    ("Next Steps", ["Board review on 4 April", "Budget sign-off by 30 April"]),
]


def _slide(title: str, lines: list[str], out: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont

    im = Image.new("RGB", (1280, 720), "white")
    draw = ImageDraw.Draw(im)
    draw.text((80, 60), title, fill="black", font=ImageFont.load_default(size=72))
    for i, line in enumerate(lines):
        draw.text((80, 240 + 90 * i), line, fill="black", font=ImageFont.load_default(size=44))
    im.save(out)


def make_lecture(out: Path, slides: int, seconds_per_slide: float) -> Path:
    """Each slide: the speaker talks about the topic, then pauses (room for a description)."""
    say, ffmpeg = shutil.which("say"), shutil.which("ffmpeg")
    if not say or not ffmpeg:
        raise SystemExit("make-lecture needs macOS `say` and ffmpeg on PATH")
    topics = (TOPICS * (slides // len(TOPICS) + 1))[:slides]
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        inputs: list[str] = []
        audio: list[str] = []
        for i, (title, lines) in enumerate(topics):
            _slide(title, lines, d / f"{i}.png")
            inputs += ["-loop", "1", "-framerate", "10", "-t", str(seconds_per_slide)]
            inputs += ["-i", str(d / f"{i}.png")]
            speech = d / f"{i}.aiff"
            subprocess.run(  # noqa: S603 - fixed argv, text from the TOPICS constant
                [say, "-o", str(speech), f"Next, {title.lower()}. Here is what changed."],
                check=True,
                timeout=60,
            )
            audio.append(str(speech))
        n = len(topics)
        for a in audio:
            inputs += ["-i", a]
        pad = "".join(
            f"[{n + i}]apad=whole_dur={seconds_per_slide},atrim=0:{seconds_per_slide}[a{i}];"
            for i in range(n)
        )
        graph = (
            "".join(f"[{i}]" for i in range(n))
            + f"concat=n={n},format=yuv420p[v];"
            + pad
            + "".join(f"[a{i}]" for i in range(n))
            + f"concat=n={n}:v=0:a=1[a]"
        )
        subprocess.run(  # noqa: S603 - argv built from constants and temp paths
            [ffmpeg, "-v", "error", "-y", *inputs, "-filter_complex", graph]
            + ["-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-c:a", "aac", str(out)],
            check=True,
            capture_output=True,
            timeout=600,
        )
    return out


def run(video: Path, api: str, timeout_s: float) -> dict[str, Any]:
    headers = {
        "X-SeeHere-Request": "1",
        "X-SeeHere-Title": quote(f"Performance run {video.stem}"),
        "X-SeeHere-Filename": quote(video.name),
        "X-SeeHere-Rights-Confirmed": "true",
    }
    with httpx.Client(base_url=api, timeout=120) as client:
        started = time.monotonic()
        r = client.post("/api/projects", content=video.read_bytes(), headers=headers)
        r.raise_for_status()
        pid = r.json()["id"]
        upload_s = time.monotonic() - started
        while True:
            status = client.get(f"/api/projects/{pid}").json()["status"]
            if status in ("ready", "failed"):
                break
            if time.monotonic() - started > timeout_s:
                raise SystemExit(f"project {pid} still {status} after {timeout_s:.0f} s")
            time.sleep(1.0)
        total_s = time.monotonic() - started
        metrics = client.get(f"/api/projects/{pid}/metrics").json()
    return {
        "project_id": pid,
        "status": status,
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "machine": f"{platform.system()} {platform.machine()}, Python {platform.python_version()}",
        "video": video.name,
        "upload_s": round(upload_s, 3),
        "upload_to_ready_s": round(total_s, 3),
        **metrics,
    }


def markdown(res: dict[str, Any]) -> str:
    out = [
        f"# Performance run: {res['video']}",
        "",
        f"All figures OBSERVED on {res['machine']} at {res['measured_at']} "
        f"(project status: {res['status']}).",
        "",
        f"- Lecture length: {res['video_duration_s']:.1f} s",
        f"- Upload request: {res['upload_s']:.2f} s",
        f"- Upload to ready (wall clock, includes queue polling): {res['upload_to_ready_s']:.1f} s",
        f"- Processing time summed over stages: {res['processing_s']:.1f} s "
        f"({res['processing_per_video_s']:.2f} s per second of lecture)",
        "",
        "| Stage | Status | Attempts | Run (s) | CPU (s) | Subprocess CPU (s) "
        "| Worker peak RSS (MB) |",
        "|---|---|---|---|---|---|---|",
    ]
    for st in res["stages"]:
        peak = st["peak_rss_mb"]
        out.append(
            f"| {st['kind']} | {st['status']} | {st['attempts']} | {st['run_s']:.2f} "
            f"| {st['cpu_s']:.2f} | {st['child_cpu_s']:.2f} "
            f"| {'' if peak is None else f'{peak:.0f}'} |"
        )
    out += ["", "## Hosted model calls", ""]
    if not res["providers"]:
        out.append("None. Every stage ran on local tools, so this run cost no API credit.")
    else:
        out += ["| Operation | Calls | Failed | Units | Mean latency (ms) | Est. cost (USD) |"]
        out += ["|---|---|---|---|---|---|"]
        for p in res["providers"]:
            units = ", ".join(f"{k} {v:g}" for k, v in p["units"].items())
            cost = p["estimated_cost_usd"]
            out.append(
                f"| {p['operation']} | {p['calls']} | {p['failed']} | {units} "
                f"| {p['mean_latency_ms']} | {'price not set' if cost is None else cost} |"
            )
    out.append("")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="seehere.bench.perf", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    mk = sub.add_parser("make-lecture", help="build a narrated slide lecture")
    mk.add_argument("out", type=Path)
    mk.add_argument("--slides", type=int, default=8)
    mk.add_argument("--seconds-per-slide", type=float, default=15.0)
    rn = sub.add_parser("run", help="upload a video and record its measurements")
    rn.add_argument("video", type=Path)
    rn.add_argument("--api", default="http://localhost:8000")
    rn.add_argument("--timeout", type=float, default=1800.0)
    rn.add_argument("--out", type=Path, help="write perf-<video>.json and .md here")
    args = p.parse_args(argv)
    if args.cmd == "make-lecture":
        print(make_lecture(args.out, args.slides, args.seconds_per_slide))
        return 0
    res = run(args.video, args.api, args.timeout)
    md = markdown(res)
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        stem = f"perf-{args.video.stem}"
        (args.out / f"{stem}.json").write_text(json.dumps(res, indent=2) + "\n")
        (args.out / f"{stem}.md").write_text(md)
        print(args.out / f"{stem}.md")
    else:
        print(md)
    return 0 if res["status"] == "ready" else 1


if __name__ == "__main__":
    sys.exit(main())
