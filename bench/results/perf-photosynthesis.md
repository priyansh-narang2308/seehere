# Performance run: photosynthesis.mp4 (Gemini vision, gemini-3.5-flash-lite)

All figures OBSERVED on Darwin arm64, Python 3.12.12 at 2026-11-14T10:46:15+00:00 (project status: ready).

- Lecture length: 96.0 s
- Upload request: 0.25 s
- Upload to ready (wall clock, includes queue polling): 25.5 s
- Processing time summed over stages: 23.3 s (0.24 s per second of lecture)

| Stage | Status | Attempts | Run (s) | CPU (s) | Subprocess CPU (s) | Worker peak RSS (MB) |
|---|---|---|---|---|---|---|
| media.prepare | succeeded | 1 | 0.50 | 0.05 | 1.08 | 193 |
| scenes.detect | succeeded | 1 | 0.10 | 0.07 | 0.00 | 1110 |
| speech.transcribe | succeeded | 1 | 5.15 | 13.24 | 0.00 | 1107 |
| ocr.extract | succeeded | 1 | 1.21 | 0.23 | 0.91 | 1112 |
| visual.analyze | succeeded | 1 | 6.15 | 0.19 | 0.00 | 1118 |
| coverage.score | succeeded | 1 | 0.03 | 0.02 | 0.00 | 1118 |
| references.resolve | succeeded | 1 | 0.03 | 0.01 | 0.00 | 1118 |
| descriptions.generate | succeeded | 1 | 0.06 | 0.03 | 0.00 | 1118 |
| claims.verify | succeeded | 1 | 0.06 | 0.02 | 0.00 | 1118 |
| schedule.plan | succeeded | 1 | 0.10 | 0.03 | 0.00 | 1118 |
| speech.synthesize | succeeded | 1 | 8.14 | 0.07 | 15.18 | 1118 |
| timing.check | succeeded | 1 | 0.03 | 0.02 | 0.00 | 1118 |
| export.build | succeeded | 1 | 1.75 | 0.20 | 5.97 | 1118 |

## Hosted model calls

| Operation | Calls | Failed | Units | Mean latency (ms) | Est. cost (USD) |
|---|---|---|---|---|---|
| vision | 7 | 0 | completion_tokens 1966, prompt_tokens 10911 | 2142 | price not set |
