# Performance run: lecture-120x15.mp4

All figures OBSERVED on Darwin arm64, Python 3.12.12 at 2026-11-14T10:07:53+00:00 (project status: ready).

- Lecture length: 1800.0 s
- Upload request: 0.14 s
- Upload to ready (wall clock, includes queue polling): 156.9 s
- Processing time summed over stages: 155.7 s (0.09 s per second of lecture)

| Stage | Status | Attempts | Run (s) | CPU (s) | Subprocess CPU (s) | Worker peak RSS (MB) |
|---|---|---|---|---|---|---|
| media.prepare | succeeded | 1 | 3.33 | 0.15 | 17.68 | 194 |
| speech.transcribe | succeeded | 1 | 114.24 | 472.19 | 0.00 | 1640 |
| scenes.detect | succeeded | 1 | 1.62 | 1.05 | 0.00 | 1640 |
| ocr.extract | succeeded | 1 | 1.36 | 0.28 | 0.98 | 1640 |
| visual.analyze | succeeded | 1 | 0.05 | 0.03 | 0.00 | 1640 |
| coverage.score | succeeded | 1 | 0.13 | 0.10 | 0.00 | 1640 |
| references.resolve | succeeded | 1 | 0.01 | 0.01 | 0.00 | 1640 |
| descriptions.generate | succeeded | 1 | 0.04 | 0.02 | 0.00 | 1640 |
| claims.verify | succeeded | 1 | 0.04 | 0.02 | 0.00 | 1640 |
| schedule.plan | succeeded | 1 | 0.10 | 0.08 | 0.00 | 1640 |
| speech.synthesize | succeeded | 1 | 11.23 | 0.14 | 17.58 | 1640 |
| timing.check | succeeded | 1 | 0.12 | 0.09 | 0.00 | 1640 |
| export.build | succeeded | 1 | 23.45 | 0.71 | 128.81 | 1640 |

## Hosted model calls

None. Every stage ran on local tools, so this run cost no API credit.
