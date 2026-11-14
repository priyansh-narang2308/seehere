# SeeHere: 35-Task Roadmap

Priority:
- **P0:** essential to a convincing working demo.
- **P1:** competition quality.
- **P2:** stretch.

Status: ✅ done · 🔄 in progress · ⏳ pending · ⏸ deferred.
Each task runs only after explicit approval ("APPROVE TASK NN").

## Time reality (see HACKATHON_REQUIREMENTS.md)
Submissions close **15 Nov**; the earliest plausible close is **12:00 IST**. Task 01 finished 13 Nov ~23:00 IST, which leaves **~37 h**.

With 34 approval-gated tasks, that averages about 1 h per task including review. That's only achievable if P0 tasks stay tight and P2 tasks are deferred. **Critical-path vertical slice:**
UPLOAD (05) → JOBS (06) → MEDIA (07) → STT (08) → SCENES (09) → OCR (10) → VISION (12) → SEEN/SAID (13) → DEIXIS (14) → LEDGER (15) → GENERATE (16) → VERIFY (17) → WINDOWS (18) → GREEDY (19) → CP-SAT (20) → TTS (22) → TIMING CHECK (23) → EXPORT (24) → PLAYER (25) → DEPLOY (34) → RELEASE (35)

**If time runs short, defer in this order:** 33 → 11 (PPTX first, then PDF) → 29/30 depth → 21 UI → 28 polish → 26 regeneration. **Never cut:** the evidence ledger, verification states, speech-safe scheduling, real TTS-duration validation, Vultr deployment, honest metrics.

## Tasks

| # | Task | P | Status | Acceptance criteria (summary) |
|---|---|---|---|---|
| 01 | Repo audit, architecture decisions, runnable foundation | P0 | ✅ | Docs created; backend `/api/health` reports real DB/binary status; web `/healthz` + status page; lint/type/tests pass |
| 02 | Design system and brand foundation | P1 | ✅ | Tokens (colour, type, spacing, radius, shadow), Radix-based primitives (Button, Input, Dialog, Tabs, Badge, Card, Toast), focus rings, reduced-motion, AA contrast verified with axe |
| 03 | Application shell and navigation | P1 | ✅ | Home, Upload, Projects, Processing, Results, Methodology routes; skip link; responsive at 375/768/1280; keyboard-only navigation works |
| 04 | Database schema and migrations | P0 | ✅ | Alembic migration creates project, media_asset, job, transcript_word/segment, frame, slide, ocr_region, visual_unit, reference_link, evidence, description_cue, verification_event, schedule_run, audio_clip, review_decision, export_artifact with FKs and indexes; up/down tested |
| 05 | Secure upload system | P0 | ✅ | Streaming upload with size cap, ffprobe-based type check, rights confirmation required, safe filenames, path-traversal tests, progress UI |
| 06 | Background jobs and orchestration | P0 | ✅ | Postgres SKIP LOCKED worker; states, progress, retries with backoff, cancellation, idempotency; tests for double-claim and crash recovery |
| 07 | Media inspection and normalization | P0 | ✅ | ffprobe metadata stored; malformed input rejected; 16 kHz WAV + frame sampling produced; subprocess argv-only with timeouts |
| 08 | Speech-to-text | P0 | ✅ | faster-whisper adapter returns words with timings on a real clip; capability marked TESTED; Vultr Whisper adapter tested for text only (if key provided) |
| 09 | Scene and slide change detection | P0 | ✅ | Keyframes with timestamps; dedupe; precision checked on the demo clip |
| 10 | OCR and text evidence | P0 | ✅ | Tesseract TSV → regions with boxes, confidence and frame; number normalization utilities tested |
| 11 | Slide deck ingestion (PDF/PPTX) | P1 | ✅ | PDF via pypdf (PyMuPDF is AGPL); PPTX parsed in memory with zip-bomb/path/XML guards; slide↔keyframe alignment by text similarity |
| 12 | Multimodal visual analysis | P0 | ✅ | Units with region boxes and per-appearance spans; schema-validated vision units from Gemini (OBSERVED live: 7 calls, 0 failed on the demo lecture) or Vultr (adapter mock-tested; live call blocked by a 401 key); keyframes analysed concurrently; OCR fallback when the model stays down |
| 13 | Seen-versus-said analysis | P0 | ✅ | Per-unit coverage score vs. transcript window; uncovered units prioritized; unit tests |
| 14 | Visual reference resolution | P0 | ✅ | Deictic phrase detection; region linking with confidence; below threshold → NEEDS REVIEW; ambiguous case in demo clip flagged, not guessed |
| 15 | Evidence ledger backend | P0 | ✅ | Full lineage query for any cue; API `GET /api/cues/{id}/evidence` |
| 16 | Description generation | P0 | ✅ | S/M/L variants from unit fields; no values absent from evidence (checked by 17) |
| 17 | Claim verification | P0 | ✅ | Four states implemented; quote/number checks against OCR + slides; unsupported numbers downgrade the cue |
| 18 | Speech windows and timing analysis | P0 | ✅ | Gap detection with padding from word timings; windows per unit |
| 19 | Greedy scheduler | P0 | ✅ | Deterministic; documented rules; validator confirms zero overlap |
| 20 | CP-SAT scheduler | P0 | ✅ | Model as documented; explanations and infeasibility reasons; compared with greedy on the same inputs |
| 21 | Extended pause planning | P1 | ✅ | Budgeted pauses with a stored reason per pause; extended timeline plan |
| 22 | TTS integration | P0 | 🟡 | Vultr TTS adapter TESTED; Piper fallback; real audio files |
| 23 | Post-synthesis timing validation | P0 | ✅ | Measured durations; re-solve ≤3 rounds; invalid cues rejected and logged |
| 24 | Export and media composition | P0 | ✅ | WebVTT, cue audio, standard MP4 (ducked), extended MP4, accessible transcript, manifest, zip |
| 25 | Accessible video player | P0 | ✅ | Plays AD audio at cue times (Web Audio/HTMLAudio sync), toggles, synced transcript, keyboard + screen reader; no duplicate descriptions |
| 26 | Instructor edit/approve workflow | P1 | ✅ | Edit, approve, reject, regenerate; edits re-verified + re-scheduled |
| 27 | Evidence ledger UI | P0 | ✅ | Frame with region overlay, OCR, slide text, transcript span, verification state per cue |
| 28 | Uncovered-content and verification report | P1 | ✅ | Described / skipped / uncovered / review / corroborated / uncertain / timing results |
| 29 | Microsoft baseline integration | P1 | ✅ | microsoft/ai-audio-descriptions licence checked, commit pinned, reproducible run script, attribution |
| 30 | Benchmark and evaluation | P1 | 🟡 | Annotation format; runner; metrics for MS / greedy / CP-SAT / reviewed; results labelled OBSERVED/SIMULATED |
| 31 | End-to-end and failure testing | P0 | ✅ | Full flow + invalid/malformed/provider-failure/interrupted-job cases |
| 32 | Security, privacy and a11y audit | P1 | 🟡 | Endpoint review, rate limits, retention job, axe + manual SR pass, fixes. Done except the screen-reader pass: keyboard and accessibility-tree checks only |
| 33 | Performance, monitoring, cost | P2 | ✅ | Measured stage timings, resource use, API spend; limits re-tuned |
| 34 | Production packaging and Vultr deploy | P0 | ✅ | Dockerfiles, prod Compose, Caddy HTTPS, health checks, volumes, cloud-init bootstrap, deploy/rollback/backup scripts ✅, verified as a full local prod stack over HTTPS; live on Vultr at https://65-20-87-43.sslip.io (demo ready in 50 s, observed) |
| 35 | Release, competition package, demo | P0 | 🟡 | README, 5 SVG diagrams, production screenshots, deployment guide, measured results, public URL https://65-20-87-43.sslip.io ✅; demo video, reach evidence and the Vultr Community submission pending |

## Flagship demo clip (self-recorded; built during Tasks 07–14)
Contains:
1. "Notice this blue line here."
2. A chart with readable values.
3. An unspoken visual detail.
4. A slide during continuous speech.
5. A short-vs-long choice for the scheduler.
6. One deliberately ambiguous reference that must be flagged.
