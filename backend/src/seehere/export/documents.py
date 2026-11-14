"""Text outputs and ffmpeg filter graphs for the export, as pure functions (no I/O).

Times: a placement starts at `start_s` on the source timeline, is heard for `audio_s`, and in
extended mode the video holds still for `pause_s` at `start_s + audio_s - pause_s` (after the
silence it could use). On the extended timeline every later moment is shifted by the pauses
before it.
"""

from __future__ import annotations

import html
from dataclasses import dataclass

from seehere.db.enums import VerificationState

STATE_LABEL = {
    VerificationState.VERIFIED_TEXT_MATCH: "verified text match",
    VerificationState.CORROBORATED: "corroborated",
    VerificationState.UNCERTAIN: "uncertain",
    VerificationState.NEEDS_REVIEW: "needs human review",
}


@dataclass(frozen=True)
class Voiced:
    """One description as it is played."""

    cue_id: str
    text: str
    start_s: float
    audio_s: float
    pause_s: float
    audio_file: str  # name inside the export
    state: VerificationState

    @property
    def pause_at_s(self) -> float:
        return round(self.start_s + self.audio_s - self.pause_s, 3)


def pauses(voiced: list[Voiced]) -> list[tuple[float, float]]:
    """(source time, length) of every video pause, merged per moment, in order."""
    merged: dict[float, float] = {}
    for v in voiced:
        if v.pause_s > 0:
            merged[v.pause_at_s] = round(merged.get(v.pause_at_s, 0.0) + v.pause_s, 3)
    return sorted(merged.items())


def to_extended(t: float, holds: list[tuple[float, float]], *, after_pause_at_t: bool) -> float:
    """Map a source time onto the extended timeline. A pause at exactly `t` counts as before
    `t` only when `after_pause_at_t` (the moment the video resumes)."""
    shift = sum(p for at, p in holds if at < t or (after_pause_at_t and at == t))
    return round(t + shift, 3)


def vtt_time(t: float) -> str:
    ms = round(t * 1000)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def webvtt(voiced: list[Voiced], *, extended: bool) -> str:
    """Description cues (WebVTT `kind="descriptions"`), one per voiced description."""
    holds = pauses(voiced) if extended else []
    out = ["WEBVTT", "Kind: descriptions", "Language: en", ""]
    for i, v in enumerate(sorted(voiced, key=lambda v: v.start_s), 1):
        start = to_extended(v.start_s, holds, after_pause_at_t=False)
        end = round(start + v.audio_s, 3)
        text = " ".join(v.text.split()).replace("-->", "→")
        out += [f"d{i}", f"{vtt_time(start)} --> {vtt_time(end)}", text, ""]
    return "\n".join(out)


def transcript_html(
    title: str,
    speech: list[tuple[float, float, str]],
    voiced: list[Voiced],
    not_voiced: list[tuple[float, str, str]],
) -> str:
    """An accessible transcript: speech and descriptions in time order, plain semantic HTML."""

    def clock(t: float) -> str:
        return f"{int(t // 60)}:{int(t % 60):02d}"

    rows = [(a, 0, f"<p>{html.escape(text)}</p>") for a, _, text in speech]
    for v in voiced:
        label = STATE_LABEL[v.state]
        rows.append(
            (
                v.start_s,
                1,
                f'<p class="description"><strong>Description:</strong> {html.escape(v.text)} '
                f"<small>({html.escape(label)})</small></p>",
            )
        )
    rows.sort(key=lambda r: (r[0], r[1]))
    items = "\n".join(
        f'<li><time datetime="PT{t:.3f}S">{clock(t)}</time> {body}</li>' for t, _, body in rows
    )
    missing = ""
    if not_voiced:
        lis = "\n".join(
            f'<li><time datetime="PT{t:.3f}S">{clock(t)}</time> {html.escape(text)} '
            f"<small>(not voiced: {html.escape(reason)})</small></li>"
            for t, text, reason in sorted(not_voiced)
        )
        missing = f"<h2>Visual content not voiced</h2>\n<ul>\n{lis}\n</ul>\n"
    name = html.escape(title)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{name}: transcript with descriptions</title>
<style>
body{{font:16px/1.6 system-ui,sans-serif;max-width:46rem;margin:2rem auto;padding:0 1rem}}
body{{color:#1a1a1a;background:#fff}}
li{{margin:.4rem 0}}li p{{display:inline}}
time{{font-family:ui-monospace,monospace;color:#555;margin-right:.5rem}}
.description{{background:#eef3ff;padding:.1rem .3rem}}
</style>
</head>
<body>
<main>
<h1>{name}</h1>
<p>Speech transcript with audio descriptions of on-screen content, in time order. The speech was
transcribed by machine and may contain errors. Each description shows how its claims were
checked against the on-screen text.</p>
<h2>Transcript</h2>
<ol>
{items}
</ol>
{missing}</main>
</body>
</html>
"""


def mix_filter(voiced: list[Voiced], first_input: int, *, duck: float) -> str:
    """Standard mode: lower the lecture audio while a description plays, then mix them in.
    Input 0 is the video; its audio is `[base]`. Output label `[aout]`."""
    if not voiced:
        return "[base]anull[aout]"
    spans = "+".join(f"between(t,{v.start_s:.3f},{v.start_s + v.audio_s:.3f})" for v in voiced)
    parts = [f"[base]volume={duck}:enable='{spans}'[ducked]"]
    labels = ["[ducked]"]
    for k, v in enumerate(voiced):
        ms = round(v.start_s * 1000)
        parts.append(f"[{first_input + k}:a]aresample=48000,adelay={ms}:all=1[d{k}]")
        labels.append(f"[d{k}]")
    parts.append(f"{''.join(labels)}amix=inputs={len(labels)}:duration=first:normalize=0[aout]")
    return ";".join(parts)


def extended_filter(voiced: list[Voiced], duration_s: float, first_input: int) -> tuple[str, float]:
    """Extended mode: cut the video at each pause, hold the frame (and silence) for the pause,
    join the pieces, and lay the descriptions on the new timeline. Inputs: 0 video, `[base]`
    its audio. Outputs `[vout]`, `[aout]` and the new duration."""
    holds = pauses(voiced)
    bounds = sorted({0.0, duration_s, *(at for at, _ in holds if 0 < at < duration_s)})
    hold_at = dict(holds)
    parts, pieces = [], []
    lead = hold_at.get(0.0, 0.0)  # a pause at the very start holds the first frame
    for i, (a, b) in enumerate(zip(bounds, bounds[1:], strict=False)):
        tail = hold_at.get(b, 0.0)
        head = lead if i == 0 else 0.0
        v = f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS"
        au = f"[base{i}]atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS"
        if head:
            v += f",tpad=start_mode=clone:start_duration={head:.3f}"
            au += f",adelay={round(head * 1000)}:all=1"
        if tail:
            v += f",tpad=stop_mode=clone:stop_duration={tail:.3f}"
            au += f",apad=pad_dur={tail:.3f}"
        parts += [f"{v}[v{i}]", f"{au}[a{i}]"]
        pieces.append(f"[v{i}][a{i}]")
    n = len(pieces)
    split = "".join(f"[base{i}]" for i in range(n))
    parts.insert(0, f"[base]asplit={n}{split}" if n > 1 else "[base]anull[base0]")
    parts.append(f"{''.join(pieces)}concat=n={n}:v=1:a=1[vcat][acat]")
    parts.append("[vcat]format=yuv420p[vout]")
    total = round(duration_s + sum(p for _, p in holds), 3)
    labels = ["[acat]"]
    for k, vd in enumerate(voiced):
        ms = round(to_extended(vd.start_s, holds, after_pause_at_t=False) * 1000)
        parts.append(f"[{first_input + k}:a]aresample=48000,adelay={ms}:all=1[d{k}]")
        labels.append(f"[d{k}]")
    parts.append(f"{''.join(labels)}amix=inputs={len(labels)}:duration=first:normalize=0[aout]")
    return ";".join(parts), total
