# Vultr Research and Architecture

Date checked: **13 Nov 2026**. Labels: **VERIFIED** (read from official docs or the public API today), **DOCUMENTED** (stated by Vultr but not yet exercised by us), **INFERRED**, **UNKNOWN**.

## 1. Sources read
| Topic | URL | Notes |
|---|---|---|
| Cloud Compute provisioning | https://docs.vultr.com/products/compute/instances/cloud-compute/provisioning | Plan categories, images, SSH keys, startup script, firewall group, automatic backups (on by default), limited (non-root) user login, Cloud-Init user data |
| Cloud Compute management | https://docs.vultr.com/products/compute/instances/cloud-compute/management | Index: hostname, OS change, reinstall, resize, restart, stop, tags, monitor, delete |
| Instance Templates | https://docs.vultr.com/products/compute/clusters/instance-templates/create | "Reusable blueprint … consistent deployments across a cluster." `POST /v2/instances/templates`, only `plan` required |
| Serverless Inference | https://docs.vultr.com/products/compute/serverless-inference | Chat, prompt and speech endpoints, plus RAG vector stores |
| Serverless Inference provisioning | https://docs.vultr.com/products/compute/serverless-inference/provisioning | Console → Compute → Serverless Inference → Create Inference. **Usage-based billing; requires acknowledging cost** |
| Serverless Inference FAQ | https://docs.vultr.com/products/compute/serverless-inference/faq | Model catalog shown in the console's model selector |
| **Public model catalog** | `GET https://api.vultrinference.com/v1/models` (no auth) | 33 models with modalities, parameters, pricing and datacenters. **VERIFIED by request** |
| **Public plan catalog** | `GET https://api.vultr.com/v2/plans?type=vc2|vhf|vhp` (no auth) | Prices, vCPU, RAM, disk, bandwidth, locations. **VERIFIED by request** |
| Regions | `GET https://api.vultr.com/v2/regions` | 33 regions, including blr (Bangalore), bom (Mumbai), del (Delhi), sjc, atl, sea |

Not yet read in full (to do in Task 34): firewall group docs, snapshots, backups pricing, the Resize, Stop and Delete articles, Object Storage, Managed Databases, Valkey, CLI/Terraform pages.

## 2. Serverless Inference: what the catalog actually says (VERIFIED from `/v1/models`)

| Need | Model (catalog id) | Catalog evidence | Gap / risk |
|---|---|---|---|
| Vision + structured JSON | `qwen3.8-flash-next` (alt: `glm-5.3-flash`, `mimo-v2.6-flash`) | Input: text, image (png/jpeg/webp/gif, url or base64, ≤20 MB), file, video. Output params include `response_format`, `structured_outputs`, `tools`. Text pricing $0.0000001/prompt token. Datacenter: sea | DOCUMENTED only. **Must test** that JSON schema output is enforced on image prompts (Task 12) |
| Speech-to-text | `whisper-large-v3-turbo`, `qwen3-asr-1.7b`, `granite-speech-5.0-2b` | Endpoint `/v1/audio/transcriptions`; input wav/mpeg base64 ≤25 MB, ≤4 h; `response_format` **only `json` or `text`**. Whisper: $0.00001111/s | **No `verbose_json` and no `timestamp_granularities` advertised, so no word-level timestamps.** This fails SeeHere's speech-safe scheduling requirement as the primary STT |
| Text-to-speech | `qwen3-tts-12hz-1.7b` (alt: `chatterbox`; `auk` is evaluation-only licence) | Voices: vivian, serena, dylan, eric, ryan, aiden, …; formats mp3/opus/flac/wav/pcm; `speed` 0.25–4; `seed`. Pricing $0.00028 per output second. Datacenter: atl | DOCUMENTED. Must test real durations (Task 22). `seed` may help reproducibility |

**Decision:**
- Vision and TTS go to **Vultr Serverless Inference** (after Task 12/22 tests).
- Word-timestamped STT runs **locally on the Compute VM with faster-whisper** (`word_timestamps=True`).
- Vultr Whisper is kept as an optional text cross-check.
- smallest.ai remains a candidate if partner access appears. Its word-timestamp support is UNKNOWN until tested.

**Cost order of magnitude (ESTIMATED):** a 3-min demo clip ≈ 30–60 frames analyzed × ~2k tokens + ~20 TTS cues × ~4 s. That is about $0.01 vision + about $0.02 TTS per run, negligible against $200. Re-check against the console's "Serverless Inference Model Prices" sheet once subscribed.

**Billing note:** creating a Serverless Inference subscription requires acknowledging usage-based cost. **It will not be created without explicit approval.**

## 3. Compute plans (VERIFIED from `/v2/plans`, 13 Nov 2026)

| Plan id | Category | vCPU | RAM | Disk | Bandwidth | $/mo | $/h | blr |
|---|---|---|---|---|---|---|---|---|
| vc2-2c-4gb | Cloud Compute (prev-gen Intel, SSD) | 2 | 4 GB | 80 GB | 3 TB | 20 | 0.027 | ✓ |
| vc2-4c-8gb | Cloud Compute | 4 | 8 GB | 160 GB | 4 TB | 40 | 0.055 | ✓ |
| vhf-3c-8gb | High Frequency (>3 GHz, NVMe) | 3 | 8 GB | 256 GB | 4 TB | 48 | 0.066 | ✓ |
| **vhp-4c-8gb-amd** | **High Performance (AMD EPYC, NVMe)** | **4** | **8 GB** | **180 GB** | **6 TB** | **48** | **0.066** | ✓ |
| vhp-4c-12gb-amd | High Performance | 4 | 12 GB | 260 GB | 7 TB | 72 | 0.099 | ✓ |
| vhp-8c-16gb-amd | High Performance | 8 | 16 GB | 350 GB | 8 TB | 96 | 0.132 | ✓ |

**Workload estimate (ESTIMATED; to be measured in Task 33):**
- faster-whisper `small.en` int8 on 4 modern vCPUs: roughly 0.3–0.6× real time, so ~1–2 min for a 3-min clip, with ~1–2 GB RAM.
- FFmpeg decode/render plus Tesseract: CPU-bound and short.
- Postgres + API + Next.js: <1.5 GB.
- 2 vCPU / 4 GB would contend between Whisper, ffmpeg and Next.js. 8 GB gives headroom.

**Selection: `vhp-4c-8gb-amd` in `blr`. TARGET, not yet approved.**
- Newest CPUs and NVMe at the same price as `vhf-3c-8gb`, with an extra vCPU.
- $48/mo ≈ $0.066/h. Running it for the whole event plus a 30-day judging tail ≈ **$48–55**, within the announced $200.
- **Fallback if processing overwhelms it:** resize to `vhp-4c-12gb-amd` or `vhp-8c-16gb-amd`, or drop to the `base.en` Whisper model. Resize procedure to be read before use.
- **Cheaper fallback if credit is limited:** `vc2-4c-8gb` at $40/mo.

Region: `blr` (team in India; Vultr Inference is US-hosted anyway, and only batch calls go there). The alternative `sjc` sits closer to the inference datacenters. This is a judgement call; latency to the API is not on the critical path.

**Billing caution (INFERRED; verify on the "Stop" and "Delete" doc pages in Task 34):** Vultr bills an instance until it is **destroyed**. Stopping it is not expected to stop charges. Automatic backups are enabled by default and may add cost. Check the price shown in the Summary panel before deploying.

## 4. Services evaluated

| Service | Decision | Reason |
|---|---|---|
| Cloud Compute (1 VM) | **Use** (mandatory) | Runs Caddy, web, API, worker and Postgres via Docker Compose |
| Serverless Inference | **Use for vision + TTS**, after tests | OpenAI-compatible, Vultr-native, cheap, and has image input + structured outputs. STT lacks word timestamps (see above) |
| Object Storage | **Reject for now** | Media is retained 24 h only, and a local Docker volume suffices for demo-scale storage. Revisit if uploads exceed disk |
| Managed PostgreSQL | **Reject** | Extra monthly cost for a single-node demo. Postgres 16 in Compose with nightly `pg_dump` is enough |
| Managed Valkey/Redis | **Reject** | The queue runs on Postgres (`SELECT … FOR UPDATE SKIP LOCKED`). One less service, and job state lives with the data |
| Clusters / Instance Templates / Kubernetes | **Reject** | Designed for multi-instance scaling. One VM is the measured need. A template could be captured after deploy for reproducibility, but it isn't required |
| Automatic backups | **Decide at deploy** | On by default. Prefer one manual snapshot after a good deploy plus `pg_dump`. Check the cost in the Summary panel |

## 5. Credit status and claiming
- Account screenshot showed **$0.00 balance, $0.00 remaining credit**. The $200 is **UNVERIFIED**.
- The event page says: "Use the Gift code shared with you to claim credits." The code is delivered by organizers (channel UNKNOWN; check email/Discord).
- To claim (to verify in console): Vultr console → **Billing** → enter the gift/promo code → confirm that the credit appears under remaining credit.
- **No paid resource will be created until the team confirms the credit is visible and approves the specific plan and region.**
