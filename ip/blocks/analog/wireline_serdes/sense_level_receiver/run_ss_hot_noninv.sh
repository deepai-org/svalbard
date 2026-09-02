#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-sense-level-receiver-ss-hot-noninv \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/sense_level_receiver/container_ss_hot_noninv.sh \
  --timeout 15m --cpus 2 --memory 4g \
  --copy result.json:serdes-sense-level-receiver-ss-hot-noninv-last.json
