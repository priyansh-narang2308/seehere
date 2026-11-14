# Performance run: photosynthesis.mp4 (Vultr Serverless Inference vision, qwen3.8-flash-next)

All figures OBSERVED on Darwin arm64, Python 3.12.12 at 2026-11-14T11:06:29+00:00 (project status: ready).

- Lecture length: 96.0 s
- Upload request: 0.17 s
- Upload to ready (wall clock, includes queue polling): 26.5 s
- Processing time summed over stages: 25.3 s (0.26 s per second of lecture)

| Stage | Status | Attempts | Run (s) | CPU (s) | Subprocess CPU (s) | Worker peak RSS (MB) |
|---|---|---|---|---|---|---|
| media.prepare | succeeded | 1 | 0.45 | 0.04 | 1.09 | 194 |
| scenes.detect | succeeded | 1 | 0.10 | 0.07 | 0.00 | 941 |
| speech.transcribe | succeeded | 1 | 4.88 | 13.03 | 0.00 | 938 |
| ocr.extract | succeeded | 1 | 1.08 | 0.20 | 0.81 | 944 |
| visual.analyze | succeeded | 1 | 7.17 | 0.21 | 0.00 | 944 |
| coverage.score | succeeded | 1 | 0.10 | 0.02 | 0.00 | 944 |
| references.resolve | succeeded | 1 | 0.02 | 0.01 | 0.00 | 944 |
| descriptions.generate | succeeded | 1 | 0.04 | 0.01 | 0.00 | 944 |
| claims.verify | succeeded | 1 | 0.04 | 0.02 | 0.00 | 944 |
| schedule.plan | succeeded | 1 | 0.08 | 0.03 | 0.00 | 944 |
| speech.synthesize | succeeded | 1 | 9.55 | 0.10 | 16.52 | 944 |
| timing.check | succeeded | 1 | 0.05 | 0.02 | 0.00 | 944 |
| export.build | succeeded | 1 | 1.70 | 0.20 | 5.51 | 944 |

## Hosted model calls

| Operation | Calls | Failed | Units | Mean latency (ms) | Est. cost (USD) |
|---|---|---|---|---|---|
| vision | 6 | 0 | completion_tokens 3836, prompt_tokens 6678 | 3831 | price not set |
