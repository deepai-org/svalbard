#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-lane-capture-restorer-ff-bias \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/lane/container_capture_restorer_ff_bias.sh \
  --timeout 30m --cpus 4 --memory 14g \
  --copy capture-restorer-ff-bias.json:serdes-lane-capture-restorer-ff-bias-last.json
