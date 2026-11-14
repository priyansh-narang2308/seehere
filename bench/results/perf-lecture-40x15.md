# Performance run: lecture-40x15.mp4

All figures OBSERVED on Darwin arm64, Python 3.12.12 at 2026-11-14T10:03:10+00:00 (project status: ready).

- Lecture length: 600.0 s
- Upload request: 0.07 s
- Upload to ready (wall clock, includes queue polling): 58.7 s
- Processing time summed over stages: 58.0 s (0.10 s per second of lecture)

| Stage | Status | Attempts | Run (s) | CPU (s) | Subprocess CPU (s) | Worker peak RSS (MB) |
|---|---|---|---|---|---|---|
| media.prepare | succeeded | 1 | 1.23 | 0.06 | 6.10 | 1699 |
| speech.transcribe | succeeded | 1 | 38.78 | 164.70 | 0.00 | 1699 |
| scenes.detect | succeeded | 1 | 0.52 | 0.32 | 0.00 | 1699 |
| ocr.extract | succeeded | 1 | 1.21 | 0.21 | 0.93 | 1699 |
| visual.analyze | succeeded | 1 | 0.02 | 0.01 | 0.00 | 1699 |
| coverage.score | succeeded | 1 | 0.03 | 0.02 | 0.00 | 1699 |
| references.resolve | succeeded | 1 | 0.01 | 0.01 | 0.00 | 1699 |
| descriptions.generate | succeeded | 1 | 0.03 | 0.01 | 0.00 | 1699 |
| claims.verify | succeeded | 1 | 0.07 | 0.05 | 0.00 | 1699 |
| schedule.plan | succeeded | 1 | 0.07 | 0.06 | 0.00 | 1699 |
| speech.synthesize | succeeded | 1 | 9.52 | 0.13 | 15.35 | 1699 |
| timing.check | succeeded | 1 | 0.10 | 0.07 | 0.00 | 1699 |
| export.build | succeeded | 1 | 6.42 | 0.32 | 31.82 | 1699 |

## Hosted model calls

None. Every stage ran on local tools, so this run cost no API credit.
