"""Build the demo lecture used for screenshots and the public demo (Task 35).

    uv run python -m seehere.bench.demo var/demo/photosynthesis.mp4

A 96-second narrated lecture (macOS `say`) over six drawn slides: a title, a labelled diagram,
a bar chart, an equation, a table and a summary. The speaker points at things without reading
them out ("look at this part here", "this chart"), and pauses after each point, which is the
situation SeeHere is built for. Everything is generated here, so the video has no third-party
rights attached.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 720
INK, MUTED, ACCENT, GREEN = (24, 28, 38), (96, 104, 120), (47, 91, 255), (46, 139, 87)


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return ImageFont.load_default(size=size)


def _canvas(title: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    d.text((80, 50), title, fill=INK, font=_font(56))
    d.line((80, 130, W - 80, 130), fill=(220, 224, 232), width=3)
    return im, d


def slide_title(out: Path) -> None:
    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    d.text((80, 250), "Photosynthesis", fill=INK, font=_font(96))
    d.text((84, 380), "Lecture 4: The light reactions", fill=MUTED, font=_font(44))
    im.save(out)


def slide_diagram(out: Path) -> None:
    im, d = _canvas("Inside a chloroplast")
    d.ellipse((140, 190, 900, 640), outline=GREEN, width=8, fill=(236, 248, 240))
    for i in range(3):  # stacks of thylakoids (grana)
        x = 260 + i * 200
        for j in range(4):
            d.rounded_rectangle((x, 330 + j * 34, x + 130, 358 + j * 34), 12, fill=GREEN)
    d.line((390, 320, 980, 230), fill=INK, width=3)
    d.text((990, 205), "Thylakoid", fill=INK, font=_font(40))
    d.line((700, 560, 980, 560), fill=INK, width=3)
    d.text((990, 535), "Stroma", fill=INK, font=_font(40))
    im.save(out)


def slide_chart(out: Path) -> None:
    im, d = _canvas("Energy captured per stage")
    base, left = 600, 200
    bars = [
        ("Light", 380, ACCENT),
        ("Electron transport", 250, ACCENT),
        ("Calvin cycle", 120, MUTED),
    ]
    for i, (label, height, color) in enumerate(bars):
        x = left + i * 300
        d.rectangle((x, base - height, x + 180, base), fill=color)
        d.text((x, base + 20), label, fill=INK, font=_font(30))
    d.line((left - 30, base, left + 900, base), fill=INK, width=3)
    d.text(
        (left - 30, 160),
        "ATP yield falls by 68% from light capture to the Calvin cycle",
        fill=INK,
        font=_font(30),
    )
    im.save(out)


def slide_equation(out: Path) -> None:
    im, d = _canvas("The overall equation")
    d.text((120, 320), "6CO2 + 6H2O  ->  C6H12O6 + 6O2", fill=INK, font=_font(64))
    d.text((120, 450), "Light energy is stored as chemical energy", fill=MUTED, font=_font(36))
    im.save(out)


def slide_table(out: Path) -> None:
    im, d = _canvas("Pigments and peak absorption")
    rows = [
        ("Pigment", "Peak (nm)"),
        ("Chlorophyll a", "430 and 662"),
        ("Chlorophyll b", "453 and 642"),
        ("Beta-carotene", "450"),
    ]
    for r, (a, b) in enumerate(rows):
        y = 200 + r * 90
        font = _font(40)
        d.text((140, y), a, fill=INK if r else MUTED, font=font)
        d.text((720, y), b, fill=INK if r else MUTED, font=font)
        d.line((120, y + 70, 1100, y + 70), fill=(220, 224, 232), width=2)
    im.save(out)


def slide_summary(out: Path) -> None:
    im, d = _canvas("Key points")
    for i, line in enumerate(
        [
            "Light reactions happen in the thylakoids",
            "They make ATP and NADPH",
            "Oxygen is released as a by-product",
        ]
    ):
        d.text((120, 210 + i * 100), f"- {line}", fill=INK, font=_font(42))
    im.save(out)


# (slide builder, what the speaker says, seconds on screen)
SCRIPT = [
    (slide_title, "Welcome back. Today we look at the light reactions of photosynthesis.", 12),
    (slide_diagram, "Look at this part here. This is where the light reactions take place.", 18),
    (slide_chart, "Now this chart. Notice how the energy changes from stage to stage.", 18),
    (slide_equation, "And here is the overall equation, which you should memorise.", 16),
    (slide_table, "These pigments absorb different colours. Take a look at the numbers.", 18),
    (slide_summary, "To sum up, the key points are on the slide.", 14),
]


def build(out: Path) -> Path:
    say, ffmpeg = shutil.which("say"), shutil.which("ffmpeg")
    if not say or not ffmpeg:
        raise SystemExit("needs macOS `say` and ffmpeg on PATH")
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        video: list[str] = []
        audio: list[str] = []
        for i, (make, line, secs) in enumerate(SCRIPT):
            make(d / f"{i}.png")
            video += ["-loop", "1", "-framerate", "10", "-t", str(secs), "-i", str(d / f"{i}.png")]
            subprocess.run(  # noqa: S603 - fixed argv, text from the SCRIPT constant
                [say, "-r", "175", "-o", str(d / f"{i}.aiff"), line], check=True, timeout=60
            )
            audio += ["-i", str(d / f"{i}.aiff")]
        n = len(SCRIPT)
        graph = "".join(f"[{i}]" for i in range(n)) + f"concat=n={n},format=yuv420p[v];"
        graph += "".join(
            f"[{n + i}]apad=whole_dur={secs},atrim=0:{secs}[a{i}];"
            for i, (_, _, secs) in enumerate(SCRIPT)
        )
        graph += "".join(f"[a{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[a]"
        subprocess.run(  # noqa: S603 - argv built from constants and temp paths
            [ffmpeg, "-v", "error", "-y", *video, *audio, "-filter_complex", graph]
            + ["-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-c:a", "aac", str(out)],
            check=True,
            capture_output=True,
            timeout=300,
        )
    return out


if __name__ == "__main__":
    print(build(Path(sys.argv[1] if len(sys.argv) > 1 else "var/demo/photosynthesis.mp4")))
