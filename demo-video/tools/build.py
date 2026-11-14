"""Assemble the SeeHere demo video from real footage, rendered cards, Kokoro narration and the score.

usage: build.py <scratch-dir> <demo-video-dir> <ws-url>
Inputs in scratch: clips/*.mp4 (screen recordings of the live site), cards/*.png, g/arch-*.png,
vo/*.wav + words.json (Kokoro af_heart narration and its Whisper word timings), dl/described.mp4 (real export).
"""

import json
import re
import subprocess
import sys
from pathlib import Path

S, D, WS = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
FPS, X = 30, 0.4  # frame rate, crossfade length
W = json.load(open(S / "words.json"))
NARR = {n["id"]: n["text"] for n in json.load(open(D / "narration.json"))}
WORK = S / "build"
WORK.mkdir(exist_ok=True)


def run(cmd):
    subprocess.run(cmd, check=True)


def dur(path):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                                capture_output=True, text=True, check=True).stdout)


VO = {k: dur(S / "vo" / f"{k}.wav") for k in NARR}


def word_t(nid, word, nth=1):
    """Start time of the nth spoken word matching `word` (case-insensitive prefix) inside narration `nid`."""
    seen = 0
    for w, a, _ in W[nid]:
        if re.sub(r"[^a-z0-9]", "", w.lower()).startswith(word.lower()):
            seen += 1
            if seen == nth:
                return a
    raise KeyError((nid, word))


# ---------------------------------------------------------------- timeline
# A segment: dict(kind=image|clip, src, dur, zoom, chips=[(png, t0, t1)], url, clip_in, speed)
segments, narr, extra_audio = [], [], []
T = 0.0  # effective start of the next segment


def seg(**kw):
    global T
    kw.setdefault("chips", [])
    kw["start"] = T
    segments.append(kw)
    T += kw["dur"] - X
    return kw["start"]


def say(nid, at):
    narr.append((nid, at))


def steps(images, triggers, end, base):
    """Image steps whose cuts land on absolute trigger times; last runs until `end`."""
    times = [base] + triggers + [end]
    for i, img in enumerate(images):
        start = times[i]
        nxt = times[i + 1]
        seg(kind="image", src=img, dur=(nxt - start) + X if i < len(images) - 1 else (nxt - start))


C = S / "cards"
G = S / "g"

# Scene 1: hook
s = seg(kind="image", src=C / "hook1.png", dur=9.0, zoom=True)
say("s1a", s + 1.5)
s = seg(kind="image", src=C / "hook2.png", dur=3.0)
say("s1b", s + 0.4)
seg(kind="image", src=C / "hook3.png", dur=12.4, zoom=True)

# Scene 2: identity
s = seg(kind="image", src=C / "title.png", dur=5.2, zoom=True)
say("s2a", s + 1.2)
a = T + 0.3
say("s2b", a)
steps([C / "pillars-1.png", C / "pillars-2.png", C / "pillars-3.png"],
      [a + word_t("s2b", "every") - 0.2, a + word_t("s2b", "placed") - 0.2], a + VO["s2b"] + 1.4, T)

# Scene 3: how it works
a = T + 0.6
b = a + VO["s3a"] + 0.6
say("s3a", a)
say("s3b", b)
steps([G / f"arch-{i}.png" for i in range(1, 9)],
      [a + word_t("s3a", "speech"), a + word_t("s3a", "slide"), b - 0.1, b + word_t("s3b", "when"),
       b + word_t("s3b", "descriptions"), b + word_t("s3b", "constraint"), b + word_t("s3b", "then")],
      b + VO["s3b"] + 1.6, T)

# Scene 4: the real product (screen recordings of https://65-20-87-43.sslip.io)
K = lambda n: C / f"overlay-chip-{n}.png"  # noqa: E731
s = seg(kind="clip", src=S / "clips/upload.mp4", clip_in=0.0, dur=18.0, chips=[(K("upload"), 0.6, 18)], url=True)
say("s4a", s + 1.2)
s = seg(kind="clip", src=S / "clips/upload.mp4", clip_in=18.0, speed=3.0, dur=18.0, chips=[(K("processing"), 0, 18)], url=True)
say("s4b", s + 0.6)
say("s4c", s + 15.3)
s = seg(kind="clip", src=S / "clips/results.mp4", clip_in=0.0, dur=27.6, chips=[(K("player"), 0.4, 27.6)], url=True)
extra_audio.append((S / "dl/described.mp4", 28.5, 14.0, s + 2.2))  # the real described-lecture audio, synced to the player
say("s4d", s + 16.6)
s = seg(kind="clip", src=S / "clips/evidence.mp4", clip_in=8.5, dur=32.0,
        chips=[(K("evidence"), 0.3, 17.2), (K("held"), 17.2, 25.4), (K("schedule"), 25.4, 32.0)], url=True)
say("s4e", s + 2.4)
say("s4f", s + 17.5)
say("s4g", s + 26.6)  # "And everything exports" lands as the exports shot begins
seg(kind="clip", src=S / "clips/exports.mp4", clip_in=0.0, dur=14.0, chips=[(K("exports"), 0, 14)], url=True)

# Scene 5: technical differentiation
a = T + 0.5
b = a + VO["s5a"] + 0.5
say("s5a", a)
say("s5b", b)
steps([C / f"diff-{i}.png" for i in (2, 3, 4, 5, 6)],
      [b - 0.1, b + word_t("s5b", "constraint") - 0.3, b + word_t("s5b", "after") - 0.2, b + word_t("s5b", "and", 2) - 0.2],
      b + VO["s5b"] + 1.2, T)

# Scene 6: Vultr deployment proof + live status page
s = seg(kind="image", src=C / "vultr.png", dur=12.6, zoom=True)
say("s6a", s + 0.7)
s = seg(kind="clip", src=S / "clips/status.mp4", clip_in=0.0, dur=13.2, crop_y=112, chips=[(K("status"), 0.3, 13.2)], url=True)
TOP_CAPTIONS = (s, s + 13.2)  # the status page's key line sits at the bottom of the frame
say("s6b", s + 0.6)

# Scene 7: closing
s = seg(kind="image", src=C / "close.png", dur=6.4, zoom=True, last=True)
say("s7a", s + 1.0)

TOTAL = segments[-1]["start"] + segments[-1]["dur"]

# sanity: narration never overlaps itself
order = sorted(narr, key=lambda x: x[1])
for (n1, t1), (n2, t2) in zip(order, order[1:]):
    assert t1 + VO[n1] + 0.15 <= t2, f"narration overlap {n1}->{n2}: {t1 + VO[n1]:.2f} > {t2:.2f}"
assert order[-1][1] + VO[order[-1][0]] < TOTAL
print(f"total {TOTAL:.2f}s, {len(segments)} segments")

# ---------------------------------------------------------------- render segments
for i, sg in enumerate(segments):
    out = WORK / f"seg{i:02d}.mp4"
    sg["file"] = out
    frames = round(sg["dur"] * FPS)
    inputs, filt = [], ""
    if sg["kind"] == "image":
        inputs = ["-loop", "1", "-framerate", str(FPS), "-i", str(sg["src"])]
        if sg.get("zoom"):
            filt = (f"[0]scale=3840:2160,zoompan=z='1+0.035*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                    f":d={frames}:s=1920x1080:fps={FPS}[v]")
        else:
            filt = "[0]scale=1920:1080,setsar=1[v]"
    else:
        sp = sg.get("speed", 1.0)
        src_len = sg["dur"] * sp
        inputs = ["-ss", f"{sg['clip_in']:.3f}", "-t", f"{src_len + 0.2:.3f}", "-i", str(sg["src"])]
        # gentle UI zoom: crop to the content column, then scale back to full HD
        filt = f"[0]setpts=(PTS-STARTPTS)/{sp},fps={FPS},crop=1720:968:100:{sg.get('crop_y', 0)},scale=1920:1080:flags=lanczos,setsar=1[v]"
    overlays = list(sg["chips"])
    if sg.get("url"):
        overlays.append((C / "overlay-url.png", 0, sg["dur"]))
    last = "v"
    for k, (png, t0, t1) in enumerate(overlays):
        inputs += ["-loop", "1", "-framerate", str(FPS), "-i", str(png)]
        fade = f"format=rgba,fade=in:st={t0}:d=0.35:alpha=1,fade=out:st={max(t0, t1 - 0.35)}:d=0.35:alpha=1"
        filt += f";[{k + 1}]{fade}[o{k}];[{last}][o{k}]overlay=0:0:enable='between(t,{t0},{t1})'[v{k}]"
        last = f"v{k}"
    run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", filt, "-map", f"[{last}]", "-frames:v", str(frames),
         "-c:v", "libx264", "-crf", "16", "-preset", "medium", "-pix_fmt", "yuv420p", "-r", str(FPS), str(out)])
    print("seg", i, sg["kind"], Path(str(sg["src"])).name, f"{sg['start']:.2f}+{sg['dur']:.2f}")

# ---------------------------------------------------------------- crossfade chain
inputs, filt, last, off = [], "", "0:v", 0.0
for i, sg in enumerate(segments):
    inputs += ["-i", str(sg["file"])]
for i in range(1, len(segments)):
    off += segments[i - 1]["dur"] - X
    filt += f"[{last}][{i}:v]xfade=transition=fade:duration={X}:offset={off:.3f}[x{i}];"
    last = f"x{i}"
filt += f"[{last}]fade=in:st=0:d=0.8,fade=out:st={TOTAL - 1.2:.3f}:d=1.2[vout]"
video = WORK / "video.mp4"
run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", filt, "-map", "[vout]", "-c:v", "libx264", "-crf", "17",
     "-preset", "medium", "-pix_fmt", "yuv420p", "-r", str(FPS), str(video)])
print("video", dur(video))

# ---------------------------------------------------------------- audio
# narration track (Kokoro af_heart), placed at absolute times
inputs, filt, labels = [], "", []
for k, (nid, at) in enumerate(narr):
    inputs += ["-i", str(S / "vo" / f"{nid}.wav")]
    ms = int(at * 1000)
    filt += f"[{k}]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms}[n{k}];"
    labels.append(f"[n{k}]")
filt += f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0,apad=whole_dur={TOTAL:.3f}[vo]"
vo = WORK / "voice.wav"
run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", filt, "-map", "[vo]", "-t", f"{TOTAL:.3f}", str(vo)])
run(["ffmpeg", "-v", "error", "-y", "-i", str(vo), "-af", "loudnorm=I=-16:TP=-1.5:LRA=7", "-ar", "48000",
     "-c:a", "libmp3lame", "-b:a", "192k", str(D / "voiceover-af-heart.mp3")])

# real described-lecture audio from the export (lecturer + SeeHere's description voice)
src, ss, ln, at = extra_audio[0]
real = WORK / "real.wav"
ms = int(at * 1000)
run(["ffmpeg", "-v", "error", "-y", "-ss", str(ss), "-t", str(ln), "-i", str(src), "-af",
     f"aresample=48000,aformat=channel_layouts=stereo,afade=in:d=0.3,afade=out:st={ln - 0.6}:d=0.6,adelay={ms}|{ms},"
     f"apad=whole_dur={TOTAL:.3f},volume=1.6", "-t", f"{TOTAL:.3f}", str(real)])

music = WORK / "music.wav"
run(["python3", str(D / "tools/make_music.py"), str(music), f"{TOTAL:.3f}"])

mix = WORK / "mix.wav"
run(["ffmpeg", "-v", "error", "-y", "-i", str(vo), "-i", str(real), "-i", str(music), "-filter_complex",
     # speech bus = narration + real product audio; music is ducked under it and dipped further while the product speaks
     "[0][1]amix=inputs=2:normalize=0[sp];[sp]asplit=2[sp1][key];"
     f"[2]volume=0.10,volume='if(between(t,{at - 0.5},{at + ln + 0.3}),0.35,1)':eval=frame[mu];"
     "[mu][key]sidechaincompress=threshold=0.02:ratio=6:attack=40:release=600:makeup=1[duck];"
     "[sp1][duck]amix=inputs=2:normalize=0[out]",
     "-map", "[out]", "-ar", "48000", str(WORK / "mix_raw.wav")])
# static gain to -15 LUFS (no dynamic loudnorm, so quiet music-only gaps are not pumped up) + true-peak limiter
meas = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(WORK / "mix_raw.wav"), "-af", "ebur128", "-f", "null", "-"],
                      capture_output=True, text=True).stderr
lufs = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", meas)[-1])
run(["ffmpeg", "-v", "error", "-y", "-i", str(WORK / "mix_raw.wav"), "-af",
     f"volume={-15 - lufs:.2f}dB,alimiter=limit=0.84:level=disabled", "-ar", "48000", str(mix)])
print("mix lufs before gain", lufs)

# ---------------------------------------------------------------- subtitles
DISPLAY = [("See Here", "SeeHere"), ("Vulture", "Vultr"), ("O C R", "OCR"), ("Web V T T", "WebVTT"),
           ("O R Tools", "OR-Tools"), ("A P I", "API"), ("H T T P S", "HTTPS"), ("ninety-six second", "96-second")]


def display(text):
    for a, b in DISPLAY:
        text = text.replace(a, b)
    return text


def chunks(text, limit=84):
    """Split into caption chunks (<= ~2 lines of 42 chars) at sentence/clause boundaries."""
    parts = re.split(r"(?<=[.!?:])\s+|(?<=,)\s+", text)
    out, cur = [], ""
    for p in parts:
        if cur and len(cur) + 1 + len(p) > limit:
            out.append(cur)
            cur = p
        else:
            cur = (cur + " " + p).strip()
    if cur:
        out.append(cur)
    final = []
    for c in out:  # hard-wrap anything still too long
        while len(c) > limit:
            cut = c.rfind(" ", 0, limit)
            final.append(c[:cut])
            c = c[cut + 1:]
        final.append(c)
    return final


cues = []
for nid, at in sorted(narr, key=lambda x: x[1]):
    words = W[nid]
    text = display(NARR[nid])
    cs = chunks(text)
    total_chars = sum(len(c) for c in cs)
    sp_start, sp_end = words[0][1], words[-1][2]
    # map chunk boundaries onto Whisper word times by character proportion
    wchars = [len(w[0]) + 1 for w in words]
    cum = [0]
    for c in wchars:
        cum.append(cum[-1] + c)
    acc = 0
    for c in cs:
        f0, f1 = acc / total_chars, (acc + len(c)) / total_chars
        acc += len(c)
        i0 = min(range(len(words)), key=lambda i: abs(cum[i] / cum[-1] - f0))
        i1 = min(range(len(words)), key=lambda i: abs(cum[i + 1] / cum[-1] - f1))
        t0 = at + (words[i0][1] if f0 > 0 else sp_start)
        t1 = at + (words[i1][2] if f1 < 1 else sp_end)
        cues.append([t0, max(t1, t0 + 0.8), c])
for a_, b_ in zip(cues, cues[1:]):  # no overlaps; small hold for readability
    a_[1] = min(max(a_[1], a_[1] + 0.25), b_[0] - 0.05)


def ts(t, sep):
    h, m = int(t // 3600), int(t % 3600 // 60)
    s_ = t % 60
    return f"{h:02d}:{m:02d}:{int(s_):02d}{sep}{int(round((s_ % 1) * 1000)) % 1000:03d}"


srt = "\n".join(f"{i + 1}\n{ts(a_, ',')} --> {ts(b_, ',')}\n{c}\n" for i, (a_, b_, c) in enumerate(cues))
(D / "subtitles.srt").write_text(srt)
(D / "subtitles.vtt").write_text("WEBVTT\n\n" + "\n".join(f"{ts(a_, '.')} --> {ts(b_, '.')}\n{c}\n" for a_, b_, c in cues))

# burned-in captions: one transparent PNG per cue, assembled into an alpha overlay track
SUB = WORK / "subs"
SUB.mkdir(exist_ok=True)
head = ("<!doctype html><html><head><meta charset='utf-8'><link href='https://fonts.googleapis.com/css2?family=Inter:wght@500;600"
        "&display=block' rel='stylesheet'><style>html,body{margin:0;width:1920px;height:1080px;background:transparent}"
        "div{position:absolute;left:50%;bottom:44px;transform:translateX(-50%);max-width:1180px;text-align:center;"
        "font:500 36px/1.38 Inter,sans-serif;color:#fff;background:rgba(6,12,31,.78);padding:12px 26px;border-radius:12px;"
        "letter-spacing:-.005em}</style></head><body>")
pairs = []
for i, (_, _, c) in enumerate(cues):
    h = SUB / f"sub-{i:03d}.html"
    pos = " style='top:150px;bottom:auto'" if TOP_CAPTIONS[0] <= cues[i][0] < TOP_CAPTIONS[1] else ""
    h.write_text(head + f"<div{pos}>{c.replace('&', '&amp;').replace('<', '&lt;')}</div></body></html>")
    pairs += [str(h), str(SUB / f"sub-{i:03d}.png")]
(SUB / "sub-blank.html").write_text(head + "</body></html>")
pairs += [str(SUB / "sub-blank.html"), str(SUB / "sub-blank.png")]
run(["python3", str(D / "tools/render_png.py"), WS, *pairs])
lines, t = ["ffconcat version 1.0"], 0.0
for i, (a_, b_, _) in enumerate(cues):
    if a_ > t:
        lines += ["file 'sub-blank.png'", f"duration {a_ - t:.3f}"]
    lines += [f"file 'sub-{i:03d}.png'", f"duration {b_ - a_:.3f}"]
    t = b_
lines += ["file 'sub-blank.png'", f"duration {TOTAL - t:.3f}", "file 'sub-blank.png'"]
(SUB / "subs.txt").write_text("\n".join(lines) + "\n")
subs = WORK / "subs.mov"
run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(SUB / "subs.txt"), "-vf", f"fps={FPS},format=argb",
     "-c:v", "qtrle", "-t", f"{TOTAL:.3f}", str(subs)])

# ---------------------------------------------------------------- final
final = D / "SeeHere_HackGlobal_Demo.mp4"
run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-i", str(subs), "-i", str(mix), "-filter_complex",
     "[0][1]overlay=0:0:format=auto,format=yuv420p[v]", "-map", "[v]", "-map", "2:a", "-c:v", "libx264", "-preset", "slow",
     "-crf", "18", "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
     "-movflags", "+faststart", "-t", f"{TOTAL:.3f}", str(final)])

json.dump({"total": TOTAL, "segments": [{k: str(v) for k, v in sg.items() if k != "file"} for sg in segments],
           "narration": [{"id": n, "at": round(t_, 2), "len": round(VO[n], 2)} for n, t_ in sorted(narr, key=lambda x: x[1])],
           "real_audio": {"from_s": extra_audio[0][1], "len_s": extra_audio[0][2], "at_s": round(extra_audio[0][3], 2)}}, open(WORK / "timeline.json", "w"), indent=1)
print("final", final, dur(final))
