# Microsoft ai-audio-descriptions baseline

| | |
|---|---|
| Project | [microsoft/ai-audio-descriptions](https://github.com/microsoft/ai-audio-descriptions) |
| Licence | MIT (Copyright (c) 2024 Microsoft); full text in [NOTICE.md](NOTICE.md) |
| Pinned commit | `be76687c6cc4ee9667328bcc380d76c1bb95ab94` (2026-08-31) |
| Tool used | `python -m cli.generate_ad input.mp4 output.vtt` (GenerateAD) |
| Status here | **UNAVAILABLE**: not run, see below |

SeeHere does not vendor, import or modify this code. `run.sh` clones it at the pinned commit into
`var/baselines/` (git-ignored), installs its own requirements into its own virtual environment,
and runs GenerateAD on a video. The WebVTT it writes is scored by `python -m seehere.bench
--microsoft-vtt` as **OBSERVED**.

## Why it is UNAVAILABLE

GenerateAD transcribes with Azure Speech and writes descriptions with an Azure OpenAI GPT
deployment. Its README provisions these with `azd provision`, which creates chargeable Azure
resources. No such resource exists for this project, and SeeHere never provisions cloud
resources automatically, so the baseline has not been run and **no Microsoft numbers are
reported**. Nothing in the benchmark estimates or simulates its output.

To run it, a person who accepts the cost provisions the resources (per the upstream README) and
sets:

```bash
export FOUNDRY_RESOURCE=...        # Foundry resource name
export FOUNDRY_RESOURCE_ID=...     # its Azure resource ID
export GPT_DEPLOYMENT=...          # GPT deployment name
```

then (sign-in through `DefaultAzureCredential`, for example `az login`):

```bash
bench/microsoft/run.sh path/to/pointers.mp4 pointers
```

Without those variables the script stops with exit code 3 before downloading anything or
calling Azure.

## How its output is compared

Each GenerateAD cue spans a narration window and holds one description. The benchmark treats the
whole cue span as heard, an upper bound on its speech overlap: RenderAD fits the synthesized audio
inside the window, but its final timing is only known after rendering. Recall and unsupported
numbers use the cue text, exactly as for SeeHere.
