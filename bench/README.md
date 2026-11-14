# Benchmark and evaluation

`python -m seehere.bench` scores every description system on an annotated lecture video and
labels every result:

- **OBSERVED**: the system really ran on this video and its output was measured;
- **SIMULATED**: computed under a stated assumption, never run end to end;
- **UNAVAILABLE**: not run (the reason is given); no numbers are reported.

## Systems

| System | Source | Evidence |
|---|---|---|
| `microsoft-ai-audio-descriptions` | GenerateAD WebVTT from [`microsoft/run.sh`](microsoft/README.md) | OBSERVED if that file is given, else UNAVAILABLE |
| `seehere-greedy` | stored greedy standard-mode schedule | OBSERVED |
| `seehere-cp-sat` | stored CP-SAT standard-mode schedule | OBSERVED |
| `seehere-extended` | stored extended-mode plan (pauses allowed) | OBSERVED |
| `seehere-reviewed` | the selected schedule after instructor review | OBSERVED when review decisions exist; otherwise SIMULATED: the scheduler re-plans in a rolled-back transaction as if a reviewer approved every held description unchanged |

## Annotation format (`seehere-bench/1`)

One JSON file per video in `annotations/`:

```json
{
  "format": "seehere-bench/1",
  "item": "pointers",
  "source_sha256": "<sha256 of the uploaded video; the runner refuses another video>",
  "duration_s": 15.0,
  "notes": "how and by whom it was annotated",
  "speech": [[0.0, 8.2], [8.93, 10.94]],
  "visuals": [
    {"id": "margin", "t_start_s": 0.0, "t_end_s": 9.0,
     "text": "Operating margin 41.7% in 2022",
     "facts": ["Operating margin", "2022"],
     "must_describe": true}
  ]
}
```

- `speech`: reference speech intervals in seconds;
- `visuals[].text`: everything the visual shows, as written (used for number support);
- `visuals[].facts`: what a description must convey because the speaker does not say it;
- `visuals[].must_describe`: false for visuals the speaker fully conveys.

## Metrics

| Metric | Meaning |
|---|---|
| Descriptions | number of descriptions voiced |
| Visual recall | share of must-describe visuals with a description started while the visual is on screen (or within 2 s after) that conveys at least one of its facts |
| Fact recall | share of must-describe facts conveyed that way (case-insensitive whole-phrase match) |
| Over speech (s) | seconds of description heard over reference speech; extended-mode pauses are not counted as heard over speech |
| Paused (s) | total time the video is held still (extended mode) |
| Unsupported numbers | numbers in descriptions that appear nowhere in the annotated on-screen text: a proxy for invented values, not a full hallucination measure |

## Run

```bash
cd backend
uv run python -m seehere.bench --annotation ../bench/annotations/pointers.json \
  --project <processed project id> [--microsoft-vtt ../var/bench/microsoft/pointers.vtt] \
  --out ../bench/results
```

## Results

[`results/pointers.md`](results/pointers.md): one 15 s synthetic item (two slides). It is a
smoke test of the pipeline and metrics, not evidence of general quality, and the annotation was
drafted by the developer rather than by independent annotators.
