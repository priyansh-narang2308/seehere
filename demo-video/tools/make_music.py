"""Synthesize the original background score: soft ambient piano + pad + a gentle pulse.

Written for this video, no samples or third-party material. Released under CC0.
usage: make_music.py <out.wav> <seconds>
"""

import sys
import wave

import numpy as np

SR = 44100
out, secs = sys.argv[1], float(sys.argv[2])
n = int(SR * secs)
t = np.arange(n) / SR
rng = np.random.default_rng(7)
BPM = 84
beat = 60 / BPM
bar = beat * 4


def midi(m):
    return 440.0 * 2 ** ((m - 69) / 12)


# I - vi - IV - V flavoured progression in D major, voiced softly (maj7 / add9 colours)
chords = [
    [50, 57, 62, 66, 69, 73],   # Dmaj7
    [47, 54, 59, 62, 66, 69],   # Bm7
    [43, 50, 55, 59, 62, 69],   # Gmaj7(9)
    [45, 52, 57, 61, 64, 71],   # A6/9
]
L = np.zeros(n)
R = np.zeros(n)


def add(sig, start, pan=0.0):
    i0 = int(start * SR)
    if i0 >= n:
        return
    seg = sig[: n - i0]
    L[i0:i0 + len(seg)] += seg * (1 - pan) * 0.5 ** 0.5 * 1.2
    R[i0:i0 + len(seg)] += seg * (1 + pan) * 0.5 ** 0.5 * 1.2


def pad(freqs, dur):
    tt = np.arange(int(dur * SR)) / SR
    env = np.minimum(1, tt / 1.8) * np.minimum(1, (dur - tt) / 1.8)
    s = sum(np.sin(2 * np.pi * f * tt + rng.uniform(0, 6)) * 0.5 + np.sin(2 * np.pi * f * 1.003 * tt) * 0.5 for f in freqs)
    return s * env / len(freqs)


def piano(f, dur=3.5):
    tt = np.arange(int(dur * SR)) / SR
    env = np.exp(-tt * 1.6) * np.minimum(1, tt / 0.004)
    s = (np.sin(2 * np.pi * f * tt) + 0.35 * np.sin(4 * np.pi * f * tt) * np.exp(-tt * 2.5)
         + 0.12 * np.sin(6 * np.pi * f * tt) * np.exp(-tt * 4))
    return s * env


def pulse(dur=0.35):
    tt = np.arange(int(dur * SR)) / SR
    f = 55 * np.exp(-tt * 9) + 42
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 11)


def tick(dur=0.08):
    tt = np.arange(int(dur * SR)) / SR
    x = rng.normal(0, 1, len(tt))
    x = np.diff(np.concatenate([[0], x]))  # crude high-pass
    return x * np.exp(-tt * 60)


nbars = int(secs / bar) + 1
for b in range(nbars):
    ch = chords[b % 4]
    t0 = b * bar
    add(pad([midi(m) for m in ch[:4]], bar + 1.8) * 0.20, t0)
    # arpeggiated piano: sparse, 8th-note feel with rests
    pattern = [0, None, 2, 3, None, 4, 3, None] if b % 2 == 0 else [1, None, 3, None, 5, 4, None, 2]
    for k, idx in enumerate(pattern):
        if idx is None or (b < 2 and k > 3):
            continue
        note = ch[idx] + 12
        add(piano(midi(note)) * 0.16, t0 + k * beat / 2, pan=(-0.35 if k % 2 else 0.35))
    if 2 <= b < nbars - 2:
        for q in range(4):
            add(pulse() * (0.20 if q in (0, 2) else 0.10), t0 + q * beat)
            add(tick() * 0.025, t0 + q * beat + beat / 2, pan=0.4)

# simple stereo reverb-ish smear (two feedback delays)
for d, g in ((0.173, 0.28), (0.311, 0.22), (0.457, 0.16)):
    k = int(d * SR)
    L[k:] += R[:-k] * g
    R[k:] += L[:-k] * g

fade = np.minimum(1, t / 3.0) * np.minimum(1, (secs - t) / 4.0)
mix = np.stack([L * fade, R * fade], axis=1)
mix /= np.max(np.abs(mix)) + 1e-9
mix *= 0.7
with wave.open(out, "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((mix * 32767).astype("<i2").tobytes())
print("music", out, secs)
