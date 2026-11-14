"""Write the HTML for every title card and overlay used in the demo video.

usage: make_cards.py <out-dir> <chart-still.png> <logo.svg> <vultr-terminal.txt>
"""

import html
import sys
from pathlib import Path

OUT, CHART, LOGO, TERM = Path(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4]
OUT.mkdir(parents=True, exist_ok=True)
URL = "65-20-87-43.sslip.io"

HEAD = """<!doctype html><html><head><meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=block" rel="stylesheet">
<style>
:root{--navy:#0B1530;--navy2:#14214A;--blue:#2F5BFF;--blue2:#6E8BFF;--ink:#0E1A33;--paper:#F4F2EC;--muted:#9FB0D9}
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1920px;height:1080px;overflow:hidden;font-family:Inter,system-ui,sans-serif;-webkit-font-smoothing:antialiased}
body.dark{background:radial-gradient(1200px 700px at 70% 20%,#16285e 0%,#0B1530 60%) ,#0B1530;color:#fff}
body.light{background:var(--paper);color:var(--ink)}
body.clear{background:transparent}
.k{font-size:20px;font-weight:700;letter-spacing:.18em;color:var(--blue2);text-transform:uppercase}
</style></head>"""


def page(name, body_class, inner):
    (OUT / f"{name}.html").write_text(f"{HEAD}<body class='{body_class}'>{inner}</body></html>")


logo_svg = Path(LOGO).read_text()
mark = ('<svg width="120" height="120" viewBox="4 4 32 32"><rect x="4" y="4" width="32" height="32" rx="8" fill="#14214A" stroke="#2F5BFF" stroke-width=".6"/>'
        '<circle cx="24" cy="15" r="6" fill="#2f5bff" fill-opacity="0.28"/><circle cx="24" cy="15" r="3.6" fill="#2f5bff"/>'
        '<rect x="11" y="24" width="18" height="2.4" rx="1.2" fill="#fff"/><rect x="11" y="19.6" width="10" height="2.4" rx="1.2" fill="#fff" fill-opacity="0.55"/></svg>')

# ---- Scene 1: hook
slide = f"<img src='file://{CHART}' style='width:1040px;border-radius:18px;box-shadow:0 30px 80px rgba(14,26,51,.18),0 0 0 1px rgba(14,26,51,.08)'>"
page("hook1", "light", f"""
<div style="position:absolute;left:120px;top:330px;width:620px">
  <div class="k" style="color:#5B6478">A lecturer says</div>
  <div style="font-size:84px;font-weight:700;letter-spacing:-.03em;line-height:1.05;margin-top:24px">“Look at<br>this chart.”</div>
</div>
<div style="position:absolute;right:110px;top:250px">{slide}</div>""")
page("hook2", "dark", f"""
<div style="position:absolute;right:110px;top:250px;filter:blur(22px) brightness(.35) saturate(.6)">{slide}</div>
<div style="position:absolute;left:120px;top:380px;width:1100px">
  <div style="font-size:88px;font-weight:700;letter-spacing:-.03em;line-height:1.05">But what if you<br>can’t see it?</div>
</div>""")
page("hook3", "dark", f"""
<div style="position:absolute;right:110px;top:250px;filter:blur(22px) brightness(.35) saturate(.6)">{slide}</div>
<div style="position:absolute;left:120px;top:330px;width:1100px">
  <div style="font-size:88px;font-weight:700;letter-spacing:-.03em;line-height:1.05">But what if you<br>can’t see it?</div>
  <div style="font-size:34px;line-height:1.45;color:#C9D4F2;margin-top:40px;width:920px">For blind and low-vision students, what is on screen but never said aloud is simply lost.</div>
</div>""")

# ---- Scene 2: identity
page("title", "dark", f"""
<div style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:34px">
  {mark}
  <div style="font-size:120px;font-weight:800;letter-spacing:-.045em">See<span style="color:var(--blue)">Here</span></div>
  <div style="font-size:40px;color:#C9D4F2;letter-spacing:-.01em">Hear what the lecture shows, not just what it says.</div>
</div>""")
pillars = [
    ("Finds what isn’t said", "Compares what is on screen with what the lecturer says, and keeps the visuals that are never spoken."),
    ("Every line has evidence", "Each description links to its frame, screen region, on-screen text and transcript moment."),
    ("Fits the pauses, reviewed by people", "Placed between stretches of speech. An instructor approves before anything is published."),
]
for n in range(1, 4):
    cards = "".join(
        f"<div style='flex:1;background:#14214A;border:1.5px solid {'#2F5BFF' if i < n else '#22325f'};border-radius:22px;padding:44px 40px;"
        f"opacity:{1 if i < n else .18}'><div style='font-size:22px;font-weight:700;color:#6E8BFF'>0{i + 1}</div>"
        f"<div style='font-size:38px;font-weight:700;letter-spacing:-.02em;margin:18px 0 18px;line-height:1.15'>{t}</div>"
        f"<div style='font-size:25px;line-height:1.5;color:#C9D4F2'>{d}</div></div>"
        for i, (t, d) in enumerate(pillars))
    page(f"pillars-{n}", "dark", f"""
<div style="position:absolute;left:120px;top:150px;display:flex;align-items:center;gap:22px">{mark.replace('120', '64')}
  <div style="font-size:52px;font-weight:800;letter-spacing:-.03em">See<span style="color:var(--blue)">Here</span></div></div>
<div style="position:absolute;left:120px;top:270px;font-size:30px;color:#C9D4F2;width:1500px;line-height:1.45">Audio descriptions for recorded lectures, for blind and low-vision students.</div>
<div style="position:absolute;left:120px;right:120px;top:420px;display:flex;gap:36px">{cards}</div>""")

# ---- Scene 5: differentiation
diffs = [
    ("Multimodal understanding", "Speech, keyframes, on-screen text and a vision model, read together."),
    ("Spoken pointers resolved", "“This” and “here” are linked to the screen region they point at."),
    ("Evidence-linked descriptions", "Written only from recorded evidence, with the link kept."),
    ("Speech-safe scheduling", "An OR-Tools CP-SAT solver places descriptions in pauses, never over the lecturer."),
    ("Measured, then re-checked", "Real voice clip lengths are measured and the plan is checked again."),
    ("Humans decide when unsure", "Uncertain claims are held back until an instructor reviews them."),
]
for n in range(1, 7):
    rows = "".join(
        f"<div style='display:flex;gap:30px;align-items:flex-start;padding:24px 0;border-top:1px solid #22325f;opacity:{1 if i < n else .14}'>"
        f"<div style='font:600 24px JetBrains Mono,monospace;color:#6E8BFF;width:60px;padding-top:6px'>0{i + 1}</div>"
        f"<div><div style='font-size:36px;font-weight:700;letter-spacing:-.02em'>{t}</div>"
        f"<div style='font-size:25px;color:#C9D4F2;margin-top:8px'>{d}</div></div></div>"
        for i, (t, d) in enumerate(diffs))
    page(f"diff-{n}", "dark", f"""
<div style="position:absolute;left:120px;top:90px"><div class="k">Methodology</div>
<div style="font-size:60px;font-weight:800;letter-spacing:-.03em;margin-top:14px">Why SeeHere is different</div></div>
<div style="position:absolute;left:120px;right:180px;top:270px;columns:2;column-gap:80px">{rows}</div>""")

# ---- Scene 6: Vultr proof (real terminal output captured from the instance)
term = html.escape(Path(TERM).read_text())
page("vultr", "dark", f"""
<div style="position:absolute;left:120px;top:90px"><div class="k">Deployment proof</div>
<div style="font-size:60px;font-weight:800;letter-spacing:-.03em;margin-top:14px">Deployed on Vultr Cloud Compute</div>
<div style="font-size:28px;color:#C9D4F2;margin-top:16px">https://{URL} · Mumbai (BOM) · 4 vCPU / 8 GB · HTTPS by Caddy + Let’s Encrypt</div></div>
<div style="position:absolute;left:120px;right:120px;top:330px;background:#060C1F;border:1px solid #22325f;border-radius:20px;overflow:hidden;box-shadow:0 30px 80px rgba(0,0,0,.45)">
  <div style="height:46px;background:#0E1733;display:flex;align-items:center;gap:10px;padding:0 20px">
    <span style="width:14px;height:14px;border-radius:50%;background:#FF5F57"></span><span style="width:14px;height:14px;border-radius:50%;background:#FEBC2E"></span><span style="width:14px;height:14px;border-radius:50%;background:#28C840"></span>
    <span style="margin-left:16px;font:500 18px JetBrains Mono,monospace;color:#8A9AC6">ssh root@seehere  (Vultr instance, captured 14 Nov 2026)</span></div>
  <pre style="font:400 23px/1.55 JetBrains Mono,monospace;color:#DCE4FF;padding:28px 32px;white-space:pre">{term}</pre>
</div>""")

# ---- Scene 7: closing
page("close", "dark", f"""
<div style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:30px">
  {mark}
  <div style="font-size:64px;font-weight:700;letter-spacing:-.03em">Making every part of a lecture accessible.</div>
  <div style="font-size:30px;color:#C9D4F2;margin-top:6px">See<b style="color:#fff">Here</b> · HackGlobal 2026 · Track 02: Multimodal &amp; Accessibility</div>
  <div style="font:500 26px JetBrains Mono,monospace;color:#6E8BFF;margin-top:10px">https://{URL}</div>
</div>""")

# ---- Overlays (transparent)
page("overlay-url", "clear", f"""
<div style="position:absolute;right:40px;bottom:150px;display:flex;align-items:center;gap:12px;background:rgba(11,21,48,.92);color:#fff;
 padding:14px 22px;border-radius:999px;font:500 22px JetBrains Mono,monospace;box-shadow:0 10px 30px rgba(0,0,0,.25)">
 <svg width="18" height="20" viewBox="0 0 18 20"><rect x="1" y="8" width="16" height="11" rx="2.5" fill="#6E8BFF"/><path d="M5 8V5.5a4 4 0 0 1 8 0V8" stroke="#6E8BFF" stroke-width="2.2" fill="none"/></svg>
 https://{URL}<span style="font-family:Inter;color:#9FB0D9;margin-left:6px">· live on Vultr</span></div>""")
chips = {
    "upload": ("1", "Upload a real lecture"),
    "processing": ("2", "Live processing on the server · shown 3× faster"),
    "player": ("3", "Described playback · real output audio"),
    "evidence": ("4", "Visual evidence ledger"),
    "held": ("5", "Uncertain claim held for review"),
    "schedule": ("6", "Speech-safe schedule"),
    "exports": ("7", "Exports and verification report"),
    "status": ("●", "Live status page"),
}
for key, (num, label) in chips.items():
    page(f"overlay-chip-{key}", "clear", f"""
<div style="position:absolute;left:40px;top:118px;display:flex;align-items:center;gap:14px;background:rgba(11,21,48,.92);color:#fff;
 padding:12px 24px 12px 12px;border-radius:999px;font:600 25px Inter;box-shadow:0 10px 30px rgba(0,0,0,.25)">
 <span style="display:inline-flex;align-items:center;justify-content:center;min-width:40px;height:40px;border-radius:999px;background:#2F5BFF;font-size:21px">{num}</span>{label}</div>""")
print("ok")
