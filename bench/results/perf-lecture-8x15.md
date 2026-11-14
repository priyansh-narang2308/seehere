# Performance run: lecture-8x15.mp4

All figures OBSERVED on Darwin arm64, Python 3.12.12 at 2026-11-14T10:01:34+00:00 (project status: ready).

- Lecture length: 120.0 s
- Upload request: 0.20 s
- Upload to ready (wall clock, includes queue polling): 33.6 s
- Processing time summed over stages: 31.4 s (0.26 s per second of lecture)

| Stage | Status | Attempts | Run (s) | CPU (s) | Subprocess CPU (s) | Worker peak RSS (MB) |
|---|---|---|---|---|---|---|
| media.prepare | succeeded | 1 | 0.49 | 0.05 | 1.30 | 195 |
| speech.transcribe | succeeded | 1 | 18.51 | 65.20 | 0.00 | 1692 |
| scenes.detect | succeeded | 1 | 0.13 | 0.08 | 0.00 | 1699 |
| ocr.extract | succeeded | 1 | 1.24 | 0.23 | 0.94 | 1699 |
| visual.analyze | succeeded | 1 | 0.02 | 0.01 | 0.00 | 1699 |
| coverage.score | succeeded | 1 | 0.02 | 0.01 | 0.00 | 1699 |
| references.resolve | succeeded | 1 | 0.01 | 0.00 | 0.00 | 1699 |
| descriptions.generate | succeeded | 1 | 0.03 | 0.01 | 0.00 | 1699 |
| claims.verify | succeeded | 1 | 0.04 | 0.02 | 0.00 | 1699 |
| schedule.plan | succeeded | 1 | 0.08 | 0.07 | 0.00 | 1699 |
| speech.synthesize | succeeded | 1 | 8.60 | 0.14 | 14.08 | 1699 |
| timing.check | succeeded | 1 | 0.10 | 0.07 | 0.00 | 1699 |
| export.build | succeeded | 1 | 2.16 | 0.23 | 6.90 | 1699 |

## Hosted model calls

None. Every stage ran on local tools, so this run cost no API credit.
