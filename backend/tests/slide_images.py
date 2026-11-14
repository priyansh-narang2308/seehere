"""Slides with known text, rendered as images, and a lecture video made from them."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# (text, font size, x, y) on a 1280x720 white slide
SLIDE_1 = [
    ("Quarterly Revenue", 72, 80, 60),
    ("Revenue rose 12.5% to $3.2M", 44, 80, 240),
    ("Operating margin 41.7% in 2022", 44, 80, 330),
]
SLIDE_2 = [("Next steps", 72, 80, 60), ("Hire 3 engineers by March", 44, 80, 240)]


def norm(t: str) -> str:
    return re.sub(r"\s+", " ", t).strip().lower()


def render(
    lines: list[tuple[str, int, int, int]], out: Path, size: tuple[int, int] = (1280, 720)
) -> dict[str, tuple[float, float, float, float]]:
    """Draw a slide; returns each line's true box as fractions of the image."""
    scale = size[0] / 1280
    im = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(im)
    boxes = {}
    for text, pt, x, y in lines:
        font = ImageFont.load_default(size=round(pt * scale))
        pos = (round(x * scale), round(y * scale))
        draw.text(pos, text, fill="black", font=font)
        x0, y0, x1, y1 = draw.textbbox(pos, text, font=font)
        boxes[text] = (x0 / size[0], y0 / size[1], (x1 - x0) / size[0], (y1 - y0) / size[1])
    im.save(out)
    return boxes


def make_deck_video(d: Path) -> Path:
    """12 s video: slide 1 (0-5 s), slide 2 (5-9 s), slide 1 again (9-12 s)."""
    render(SLIDE_1, d / "1.png")
    render(SLIDE_2, d / "2.png")
    out = d / "deck.mp4"
    parts = []
    for img, secs in [("1.png", 5), ("2.png", 4), ("1.png", 3)]:
        parts += ["-loop", "1", "-framerate", "10", "-t", str(secs), "-i", str(d / img)]
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", *parts, "-f", "lavfi", "-i", "sine=duration=12"]
        + ["-filter_complex", "[0][1][2]concat=n=3,format=yuv420p[v]", "-map", "[v]"]
        + ["-map", "3:a", "-c:v", "libx264", "-c:a", "aac", "-shortest", str(out)],
        check=True,
        capture_output=True,
        timeout=120,
    )
    return out
