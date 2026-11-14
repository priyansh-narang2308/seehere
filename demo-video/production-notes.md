# Production notes: SeeHere HackGlobal 2026 demo

## Output

| File | Spec |
|---|---|
| `SeeHere_HackGlobal_Demo.mp4` | 4:16.4. H.264 High, 1920×1080, 30 fps, CRF 18, yuv420p, faststart. AAC 256 kb/s, 48 kHz stereo. 37 MB. Subtitles burned in. |
| `voiceover-af-heart.mp3` | The narration track on its own, placed on the final timeline. MP3 192 kb/s, normalised to −16 LUFS. |
| `subtitles.srt` / `subtitles.vtt` | 52 cues. The text is the approved script; the timing comes from Whisper word timestamps of the rendered narration. |
| `system-architecture.svg` | The architecture graphic used in scene 03, written as SVG by `tools/make_arch.py`. It does not use Mermaid. |

## Feature verification checklist (live site, 14 Nov 2026)

Every feature below was checked on https://65-20-87-43.sslip.io before it was filmed. The video shows only these.

| Feature | Verified | Shown |
|---|---|---|
| Upload with the rights checkbox; size, format and duration checks | ✅ Real upload of `photosynthesis.mp4`, 96 s, 456 KB | 1:27 |
| 14-stage queued pipeline with live per-stage status | ✅ Every stage went Running → Done; ready about 55 s after upload | 1:45 (3× speed, labelled) |
| Speech-to-text with word timings (faster-whisper) | ✅ Transcript with timestamps on the Results page | 2:03 |
| Slide-change keyframes, OCR and the vision model on Vultr Serverless Inference | ✅ 6 keyframes; `/api/metrics` vision calls went from 12 to 18 for this run, 0 failed | 1:45 and 4:00 |
| Described playback in standard mode, with the voice placed in pauses | ✅ Real `lecture-described.mp4` export audio | 2:05–2:19 |
| Visual evidence ledger: keyframe crop, OCR quotes, claim-by-claim verification | ✅ | 2:30 |
| Uncertain claim held for review (the equation the OCR misread) | ✅ "Needs human review · held until approved" | 2:47 |
| CP-SAT speech-safe schedule, compared with greedy | ✅ "9 of 11 descriptions fit… CP-SAT placed 9" | 2:56 |
| Exports and coverage/verification report | ✅ All 9 files built | 3:01 |
| Live status page: health, stage timings, hosted-model calls | ✅ | 3:57 |
| Hosting on Vultr Cloud Compute | ✅ Vultr metadata service reports region BOM; all compose services up; `/api/health` returns ok/production | 3:45 |

**Not shown**
- **Slide-deck (PDF/PPTX) matching.** It is implemented and appears as an optional section on the Processing page, but the demo lecture has no deck, so it was not filmed.
- **Instructor Approve/Edit/Reject buttons.** They are visible but were not clicked.
- **The Vultr web console.** The owner's account was not used. Deployment proof comes from the instance itself instead.

## Tools

- **Narration:** Kokoro TTS through [`kokoro-onnx`](https://github.com/thewh1teagle/kokoro-onnx) with the `kokoro-v1.0.onnx` model and `voices-v1.0.bin`. Voice **`af_heart`**, `speed=0.95`, `lang="en-us"`. There are 18 segments and every one uses `af_heart`; no other TTS was used.
- **Narration QC:** every segment was transcribed back with faster-whisper `small.en`.
  - Two lines were misheard: "said aloud" was heard as "set out loud", and "misread" as "must read". Both lines were reworded and regenerated, and the re-transcription was correct.
  - The same word timestamps drive the subtitle timing and the step-by-step diagram reveals.
- **Footage:** headless Google Chrome, driven over the DevTools Protocol by `Page.startScreencast`.
  - The viewport is 1440×810 at a device scale of 1.333, so frames are captured at 1920×1080.
  - Frames were saved with their real arrival times and converted to constant 30 fps with ffmpeg concat durations.
  - The upload uses `DOM.setFileInputFiles` with the real demo file. Typing and clicks are real CDP input events.
- **Cards and graphics:** HTML/SVG rendered to PNG by the same headless Chrome, using Inter and JetBrains Mono.
- **Edit, mix and encode:** ffmpeg 9.0, driven by `tools/build.py`.
  - Picture: per-shot renders, then a chain of 0.4 s `xfade` crossfades.
  - Audio: side-chain ducking, then a static gain to −15 LUFS and a true-peak limiter.
  - Captions: a burned-in alpha overlay built from one rendered PNG per cue.
- **Music:** `tools/make_music.py`, original and CC0. See `background-music-license.md`.

## What was edited, and how (for honesty)

- **Processing speed.** The processing stretch, from the upload landing on the Processing page until Ready, is played at **3×** and labelled "shown 3× faster" on screen. Nothing was cut out of it, and its progress is the page's own.
- **Cursor and click ring.** These are drawn by a small script injected into the page, because headless Chrome has no visible pointer. The clicks themselves are real input events.
- **UI zoom.** Every product shot is cropped to 1720×968 and scaled to 1080p, a 1.12× zoom, so the interface text is easier to read.
- **Status page.** That shot is cropped 112 px lower so its "Hosted model calls" line stays in frame, and its captions are moved to the top.
- **Playback audio.** The recording itself is silent. The audio under the player shot is that project's own `lecture-described.mp4` export, aligned to the moment the player starts at 0:28.5.
- **Badges.** The URL badge and step chips are overlays added in the edit. Every product pixel underneath them comes from the live site.
- **Terminal card.** Its text was captured verbatim over SSH from the instance (`evidence/vultr-terminal.txt`). To print the outputs, `jq` was installed on the server with `apt-get install jq`. That was the only change made to the server for the video.
- **Site text fix.** Before filming, a stale line on the Processing page, "optional vision model (not yet live-tested)", was corrected to say the vision model is live on Vultr. The fix was committed and redeployed with `deploy/deploy.sh`.

## Final QC

| Check | Result |
|---|---|
| Runtime | 256.4 s (4:16), within the 4:50 maximum |
| Streams | h264 1920×1080 at 30/1, plus AAC 48 kHz stereo |
| Loudness | −15.8 LUFS integrated, −1.0 dBFS peak. Voice sections average about −19.5 dB; music-only passages about −31 dB |
| Voice | `af_heart` throughout. Whisper re-transcription of 2:00–2:50 of the final mix matches the script and the product audio |
| Subtitles | Spot-checked against the frames at 25+ points. The cues follow the word timings and never overlap |
| URL | `https://65-20-87-43.sslip.io` is shown in the URL badge, the Vultr card and the closing card |
| Secrets | No API keys, passwords or tokens appear. The status page reads "keys present … vultr-inference", a label without the key. The only IP shown is the public one already in the URL |
| Architecture diagram | Matches the implemented jobs in `backend/src/seehere/` and the deployment in `deploy/docker-compose.prod.yml` |

## Rebuild

```bash
python3 tools/make_arch.py system-architecture.svg <scratch>/g
python3 tools/make_cards.py <scratch>/cards <chart.png> ../docs/assets/seehere-logo.svg evidence/vultr-terminal.txt
python3 tools/render_png.py <chrome-ws> <scratch>/cards/*.html …
python3 tools/build.py <scratch> . <chrome-ws>
```

Recordings of the live site are in `evidence/footage/` and stills in `evidence/stills/`. Project ids are in `evidence/projects.md`.
