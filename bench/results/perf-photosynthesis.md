# Performance run: photosynthesis.mp4

All figures OBSERVED on Darwin arm64, Python 3.12.12 at 2026-11-14T10:28:19+00:00 (project status: ready).

- Lecture length: 96.0 s
- Upload request: 0.20 s
- Upload to ready (wall clock, includes queue polling): 19.4 s
- Processing time summed over stages: 18.5 s (0.19 s per second of lecture)

| Stage | Status | Attempts | Run (s) | CPU (s) | Subprocess CPU (s) | Worker peak RSS (MB) |
|---|---|---|---|---|---|---|
| media.prepare | succeeded | 1 | 0.51 | 0.05 | 1.13 | 194 |
| scenes.detect | succeeded | 1 | 0.11 | 0.07 | 0.00 | 1120 |
| speech.transcribe | succeeded | 1 | 4.28 | 12.18 | 0.00 | 1120 |
| ocr.extract | succeeded | 1 | 1.03 | 0.19 | 0.78 | 1120 |
| visual.analyze | succeeded | 1 | 5.07 | 0.16 | 0.00 | 1120 |
| coverage.score | succeeded | 1 | 0.03 | 0.01 | 0.00 | 1120 |
| references.resolve | succeeded | 1 | 0.01 | 0.01 | 0.00 | 1120 |
| descriptions.generate | succeeded | 1 | 0.04 | 0.02 | 0.00 | 1120 |
| claims.verify | succeeded | 1 | 0.04 | 0.02 | 0.00 | 1120 |
| schedule.plan | succeeded | 1 | 0.06 | 0.02 | 0.00 | 1120 |
| speech.synthesize | succeeded | 1 | 5.76 | 0.09 | 11.06 | 1120 |
| timing.check | succeeded | 1 | 0.04 | 0.01 | 0.00 | 1120 |
| export.build | succeeded | 1 | 1.57 | 0.18 | 5.47 | 1120 |

## Hosted model calls

| Operation | Calls | Failed | Units | Mean latency (ms) | Est. cost (USD) |
|---|---|---|---|---|---|
| vision | 6 | 0 | completion_tokens 1571, prompt_tokens 9102 | 2818 | price not set |
