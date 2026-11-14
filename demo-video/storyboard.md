# Storyboard — SeeHere HackGlobal 2026 demo

Final runtime **4:16.36** · 1920×1080 · 30 fps · 0.4 s crossfades between every shot.

Scene budget vs. brief: hook 0:00–0:23 · intro 0:23–0:46 · how it works 0:46–1:27 · **live product 1:27–3:15** · differentiation 3:15–3:45 · Vultr proof + status page 3:45–4:10 · close 4:10–4:16.

| Scene | Start | Length | Source | Shot |
|---|---|---|---|---|
| 01 | 0:00.00 | 9.00s | `hook1.png` | Warm-paper card. "A lecturer says: “Look at this chart.”" beside the real chart slide from the demo lecture (frame at 0:31). Slow push-in. |
| 01 | 0:08.60 | 3.00s | `hook2.png` | Cut to navy; the same slide blurs and darkens. "But what if you can’t see it?" |
| 01 | 0:11.20 | 12.40s | `hook3.png` | Line added: what is on screen but never said is lost for blind and low-vision students. |
| 02 | 0:23.20 | 5.20s | `title.png` | SeeHere mark, wordmark and tagline reveal. |
| 02 | 0:28.00 | 8.90s | `pillars-1.png` | Three product pillars reveal one by one in sync with the narration. |
| 02 | 0:36.50 | 3.00s | `pillars-2.png` | Pillar 2: every line has evidence. |
| 02 | 0:39.10 | 6.90s | `pillars-3.png` | Pillar 3: fits the pauses, reviewed by people. |
| 03 | 0:45.60 | 5.70s | `arch-1.png` | Architecture diagram (system-architecture.svg), reveal step 1/8 on the word that names it. |
| 03 | 0:50.90 | 3.46s | `arch-2.png` | Architecture diagram (system-architecture.svg), reveal step 2/8 on the word that names it. |
| 03 | 0:53.96 | 11.59s | `arch-3.png` | Architecture diagram (system-architecture.svg), reveal step 3/8 on the word that names it. |
| 03 | 1:05.15 | 5.88s | `arch-4.png` | Architecture diagram (system-architecture.svg), reveal step 4/8 on the word that names it. |
| 03 | 1:10.63 | 5.06s | `arch-5.png` | Architecture diagram (system-architecture.svg), reveal step 5/8 on the word that names it. |
| 03 | 1:15.29 | 5.06s | `arch-6.png` | Architecture diagram (system-architecture.svg), reveal step 6/8 on the word that names it. |
| 03 | 1:19.95 | 3.42s | `arch-7.png` | Architecture diagram (system-architecture.svg), reveal step 7/8 on the word that names it. |
| 03 | 1:22.97 | 4.91s | `arch-8.png` | Architecture diagram (system-architecture.svg), reveal step 8/8 on the word that names it. |
| 04 | 1:27.49 | 18.00s | `upload.mp4` (source 0.0s) | LIVE SITE. Home → Upload → real file picked, title typed, permission ticked, Upload clicked. URL badge on screen. |
| 04 | 1:45.09 | 18.00s | `upload.mp4` (source 18.0s, ×3.0) | LIVE SITE. Real processing on the server, shown 3× faster (labelled): every stage turns from Running to Done; keyframes and the vision step appear. |
| 04 | 2:02.69 | 27.60s | `results.mp4` (source 0.0s) | LIVE SITE. Results page: player plays 0:28.5–0:42.5 with the real described audio; transcript with descriptions. |
| 04 | 2:29.89 | 32.00s | `evidence.mp4` (source 8.5s) | LIVE SITE. Descriptions with verification states → Show evidence on the bar chart (keyframe crop, OCR quotes, claim checks) → equation held for human review → CP-SAT schedule. |
| 04 | 3:01.49 | 14.00s | `exports.mp4` (source 0.0s) | LIVE SITE. Downloads list (zip, described MP4s, WebVTT, transcript, audio clips, report, manifest) → coverage and verification report. |
| 05 | 3:15.09 | 5.10s | `diff-2.png` | "Why SeeHere is different": six principles revealed with the narration. |
| 05 | 3:19.78 | 7.84s | `diff-3.png` | Principle 3: evidence-linked descriptions. |
| 05 | 3:27.22 | 8.56s | `diff-4.png` | Principle 4: speech-safe scheduling (OR-Tools CP-SAT). |
| 05 | 3:35.38 | 3.74s | `diff-5.png` | Principle 5: measured, then re-checked. |
| 05 | 3:38.72 | 6.64s | `diff-6.png` | Principle 6: humans decide when unsure. |
| 06 | 3:44.96 | 12.60s | `vultr.png` | "Deployed on Vultr Cloud Compute": verbatim terminal output captured over SSH from the instance — Vultr metadata region BOM, docker compose services healthy, /api/health ok/production. |
| 06 | 3:57.16 | 13.20s | `status.mp4` (source 0.0s) | LIVE SITE. /status: component health, measured stage timings, hosted model calls (Vultr vision call count and latency). Captions moved to the top here. |
| 07 | 4:09.96 | 6.40s | `close.png` | Closing card: "Making every part of a lecture accessible." SeeHere · HackGlobal 2026 · Multimodal & Accessibility · URL. |

Narration placement (seconds) is in `evidence/timeline.json`; the text is in `narration-script.md`.
