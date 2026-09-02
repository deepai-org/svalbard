#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-sense-level-receiver-ss-hot-schmitt \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/sense_level_receiver/container_ss_hot_schmitt.sh \
  --timeout 20m --cpus 2 --memory 4g \
  --copy result.json:serdes-sense-level-receiver-ss-hot-schmitt-last.json \
  --copy manifest.json:serdes-sense-level-receiver-ss-hot-schmitt-manifest-last.json
