#!/usr/bin/env bash
# Run the Microsoft ai-audio-descriptions baseline (GenerateAD) on one video, reproducibly.
#
#   bench/microsoft/run.sh path/to/video.mp4 [item-name]
#
# Writes var/bench/microsoft/<item>.vtt, which `python -m seehere.bench --microsoft-vtt`
# scores as OBSERVED. GenerateAD calls Azure Speech and an Azure OpenAI (GPT) deployment, which
# are chargeable. This script never provisions or changes anything in Azure: it stops with
# UNAVAILABLE unless the configuration below is already set (see bench/microsoft/README.md).
set -euo pipefail

REPO_URL="https://github.com/microsoft/ai-audio-descriptions.git"
PINNED_COMMIT="be76687c6cc4ee9667328bcc380d76c1bb95ab94"  # 2026-08-31, MIT licence

here="$(cd "$(dirname "$0")" && pwd)"
root="$(cd "$here/../.." && pwd)"
video="${1:?usage: bench/microsoft/run.sh VIDEO.mp4 [ITEM]}"
item="${2:-$(basename "${video%.*}")}"
checkout="$root/var/baselines/ai-audio-descriptions"
out_dir="$root/var/bench/microsoft"

[[ -f "$video" ]] || { echo "error: no such video: $video" >&2; exit 2; }

# 1. Configuration first: nothing is downloaded and no Azure call is made without it.
missing=()
for name in FOUNDRY_RESOURCE FOUNDRY_RESOURCE_ID GPT_DEPLOYMENT; do
  [[ -n "${!name:-}" ]] || missing+=("$name")
done
if (( ${#missing[@]} )); then
  echo "UNAVAILABLE: Microsoft baseline not run. Missing: ${missing[*]}." >&2
  echo "It needs an Azure Foundry resource (Speech + GPT deployment), which is chargeable." >&2
  echo "Provision it yourself if you choose to, then export the variables and retry." >&2
  exit 3
fi
for tool in git uv ffmpeg ffprobe; do
  command -v "$tool" >/dev/null || { echo "error: $tool is not installed" >&2; exit 2; }
done

# 2. The pinned source, verified.
if [[ ! -d "$checkout/.git" ]]; then
  git clone --quiet --filter=blob:none "$REPO_URL" "$checkout"
fi
git -C "$checkout" fetch --quiet origin "$PINNED_COMMIT"
git -C "$checkout" checkout --quiet --detach "$PINNED_COMMIT"
[[ "$(git -C "$checkout" rev-parse HEAD)" == "$PINNED_COMMIT" ]] || {
  echo "error: checkout is not at the pinned commit" >&2; exit 2; }

# 3. Its own environment (never mixed with SeeHere's), then GenerateAD.
if [[ ! -x "$checkout/.venv/bin/python" ]]; then
  uv venv --quiet "$checkout/.venv"
  uv pip install --quiet --python "$checkout/.venv/bin/python" -r "$checkout/requirements.txt"
fi
mkdir -p "$out_dir"
abs_video="$(cd "$(dirname "$video")" && pwd)/$(basename "$video")"
(cd "$checkout" && .venv/bin/python -m cli.generate_ad "$abs_video" "$out_dir/$item.vtt")
echo "$out_dir/$item.vtt"
echo "Score it: cd backend && uv run python -m seehere.bench --annotation ../bench/annotations/$item.json --project <id> --microsoft-vtt $out_dir/$item.vtt"
