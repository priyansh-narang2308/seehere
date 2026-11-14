"""Generate demo-video/system-architecture.svg: the implemented SeeHere pipeline on Vultr.

Each node belongs to a group g1..g8 so the video can reveal the flow step by step.
"""

import sys
from pathlib import Path

NAVY, CARD, LINE, BLUE, TEXT, MUTED = "#0B1530", "#14214A", "#2A3A6E", "#2F5BFF", "#FFFFFF", "#9FB0D9"

W, H = 1920, 1080
nodes = {
    # id: (x, y, w, h, title, sub, group, style)
    "video": (110, 300, 255, 110, "Lecture video", "MP4 · MOV · MKV · WebM", 1, "in"),
    "deck": (110, 450, 255, 90, "Slide deck", "PDF / PPTX · optional", 1, "opt"),
    "prep": (420, 360, 275, 110, "Prepare media", "ffmpeg · 16 kHz audio · 1 fps", 1, "n"),
    "stt": (760, 250, 320, 110, "Speech-to-text", "faster-whisper · word timings", 2, "n"),
    "scenes": (760, 430, 280, 110, "Slide changes", "keyframes, duplicates merged", 3, "n"),
    "ocr": (1080, 430, 265, 110, "On-screen text", "Tesseract OCR + positions", 3, "n"),
    "vision": (1385, 430, 300, 110, "Vision model", "Vultr Serverless Inference", 3, "vultr"),
    "cover": (1500, 250, 300, 110, "Seen vs said", "what is shown, never spoken", 4, "acc"),
    "refs": (110, 680, 275, 110, "Resolve pointers", "“this”, “here” → screen region", 5, "n"),
    "write": (420, 680, 255, 110, "Write descriptions", "only from evidence", 6, "n"),
    "verify": (710, 680, 265, 110, "Verify claims", "quotes &amp; numbers vs OCR", 6, "acc"),
    "sched": (1010, 680, 275, 110, "Schedule in pauses", "OR-Tools CP-SAT solver", 7, "acc"),
    "tts": (1320, 680, 210, 110, "Voice", "Piper TTS · measured", 8, "n"),
    "timing": (1565, 680, 270, 110, "Timing check", "re-plan with real lengths", 8, "n"),
    "review": (710, 880, 300, 100, "Instructor review", "approve · edit · reject", 8, "n"),
    "export": (1040, 880, 420, 100, "Accessible playback + exports", "WebVTT · described MP4 · transcript · report", 8, "acc"),
}
edges = [
    ("video", "prep", 1), ("deck", "prep", 1), ("prep", "stt", 2), ("prep", "scenes", 3),
    ("scenes", "ocr", 3), ("ocr", "vision", 3), ("stt", "cover", 4), ("vision", "cover", 4),
    ("cover", "refs", 5), ("refs", "write", 6), ("write", "verify", 6), ("verify", "sched", 7),
    ("sched", "tts", 8), ("tts", "timing", 8), ("timing", "export", 8), ("verify", "review", 8),
    ("review", "export", 8),
]


def anchor(n, side):
    x, y, w, h = nodes[n][:4]
    return {"r": (x + w, y + h / 2), "l": (x, y + h / 2), "t": (x + w / 2, y), "b": (x + w / 2, y + h)}[side]


def path(a, b):
    ax, ay, aw, ah = nodes[a][:4]
    bx, by, bw, bh = nodes[b][:4]
    if a == "cover" and b == "refs":
        sx, sy = anchor(a, "r")
        ex, ey = anchor(b, "t")
        return f"M{sx} {sy} H1850 V620 H{ex} V{ey - 6}"
    if a == "timing" and b == "export":
        sx, sy = anchor(a, "b")
        ex, ey = anchor(b, "r")
        return f"M{sx} {sy} V{ey} H{ex + 6}"
    if a == "verify" and b == "review":
        sx, sy = anchor(a, "b")
        ex, ey = anchor(b, "t")
        return f"M{sx} {sy} V{ey - 6}"
    if a == "vision" and b == "cover":
        sx, sy = anchor(a, "t")
        ex, ey = anchor(b, "b")
        return f"M{sx} {sy} C{sx} {sy - 40} {ex} {ey + 40} {ex} {ey + 6}"
    sx, sy = anchor(a, "r")
    ex, ey = anchor(b, "l")
    if abs(sy - ey) < 2:
        return f"M{sx} {sy} H{ex - 6}"
    mx = (sx + ex) / 2
    return f"M{sx} {sy} C{mx} {sy} {mx} {ey} {ex - 6} {ey}"


def build(step: int | None = None) -> str:
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t d">',
        '<title id="t">SeeHere system architecture on Vultr</title>',
        '<desc id="d">A lecture video, and optionally its slide deck, is prepared into audio and frames. Speech is transcribed with word '
        'timings. Slide changes become keyframes, on-screen text is read with OCR and a vision model on Vultr Serverless Inference '
        'finds charts, tables and diagrams. Seen-versus-said finds visuals that are never spoken; spoken pointers are resolved to '
        'regions. Descriptions are written from evidence only, claims are verified, a CP-SAT solver schedules them in speech pauses, '
        'Piper voices them, timing is re-checked with measured audio, an instructor reviews them, and accessible exports are built. '
        'Everything runs on one Vultr Cloud Compute instance with Docker Compose.</desc>',
        f'<defs><marker id="a" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="{BLUE}"/></marker>',
        '<style>text{font-family:Inter,"Segoe UI",Helvetica,Arial,sans-serif}'
        f'.h{{font-size:24px;font-weight:650;fill:{TEXT}}} .s{{font-size:17px;fill:{MUTED}}}'
        f'.e{{fill:none;stroke:{BLUE};stroke-width:2.4;stroke-opacity:.85}}'
        '.dim{opacity:.12}</style></defs>',
        f'<rect width="{W}" height="{H}" fill="{NAVY}"/>',
        # Vultr host container
        f'<rect x="60" y="150" width="1800" height="880" rx="28" fill="none" stroke="{LINE}" stroke-width="2" stroke-dasharray="10 8"/>',
        f'<rect x="90" y="132" width="660" height="38" rx="19" fill="{NAVY}"/>',
        f'<text x="110" y="160" style="font-size:20px;font-weight:700;letter-spacing:.12em;fill:#6E8BFF">VULTR CLOUD COMPUTE · DOCKER COMPOSE · HTTPS</text>',
        f'<text x="60" y="80" style="font-size:44px;font-weight:700;fill:{TEXT}">How SeeHere works</text>',
        f'<text x="60" y="118" style="font-size:22px;fill:{MUTED}">Each box is a queued job on the server. Every description keeps a link back to its evidence.</text>',
        f'<text x="760" y="236" style="font-size:16px;font-weight:700;letter-spacing:.14em;fill:#6E8BFF">HEARING</text>',
        f'<text x="760" y="584" style="font-size:16px;font-weight:700;letter-spacing:.14em;fill:#6E8BFF">SEEING</text>',
    ]
    for a, b, g in edges:
        cls = "e" + (" dim" if step is not None and g > step else "")
        dash = ' stroke-dasharray="6 6"' if a == "deck" else ""
        out.append(f'<path d="{path(a, b)}" class="{cls}"{dash} marker-end="url(#a)"/>')
    for nid, (x, y, w, h, title, sub, g, style) in nodes.items():
        dim = ' class="dim"' if step is not None and g > step else ""
        fill, stroke, sw, dash = CARD, LINE, 2, ""
        if style == "acc":
            fill, stroke = "#16286A", BLUE
        if style == "vultr":
            fill, stroke, sw = "#0F2C8F", "#5C7CFF", 3
        if style == "opt":
            dash = ' stroke-dasharray="8 6"'
        if style == "in":
            fill = "#1B2B5C"
        out.append(f'<g{dim}><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{dash}/>')
        cy = y + h / 2
        out.append(f'<text x="{x + 22}" y="{cy - 6}" class="h">{title}</text>')
        out.append(f'<text x="{x + 22}" y="{cy + 24}" class="s">{sub}</text></g>')
    # evidence ledger band
    dim = ' class="dim"' if step is not None and step < 6 else ""
    out.append(f'<g{dim}><rect x="110" y="880" width="540" height="100" rx="16" fill="#0E1A3D" stroke="#6E8BFF" stroke-width="2"/>'
               f'<text x="132" y="922" class="h">Visual evidence ledger</text>'
               f'<text x="132" y="952" class="s">frame · region · OCR text · slide · transcript</text></g>')
    out.append("</svg>")
    return "\n".join(out)


if __name__ == "__main__":
    out = Path(sys.argv[1])
    out.write_text(build())
    if len(sys.argv) > 2:
        d = Path(sys.argv[2])
        d.mkdir(parents=True, exist_ok=True)
        for s in range(1, 9):
            (d / f"arch-{s}.svg").write_text(build(s))
