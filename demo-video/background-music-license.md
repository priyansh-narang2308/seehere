# Background music — source and license

**Track:** "SeeHere Theme" (untitled ambient score), 4:16, stereo, 44.1 kHz.

**Source:** composed and synthesized for this video by [`tools/make_music.py`](tools/make_music.py). It is generated entirely from code — sine-based piano tones, a detuned pad, a soft low pulse and filtered-noise ticks over a D major I–vi–IV–V progression at 84 BPM. No samples, loops, stock libraries or third-party recordings are used, and no AI music service was involved.

**License:** dedicated to the public domain under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/). No attribution is required.

**Reproduce:** `python3 tools/make_music.py music.wav 256.4` (fixed random seed, so the output is identical).

**Mix:** the score sits about 11–12 dB below the narration in music-only passages and is side-chain ducked further under speech. During the 14 s of real product audio it is dipped by another ~9 dB. Final programme loudness is −15.8 LUFS integrated, −1.0 dBFS peak.
