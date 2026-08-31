#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label wifi-if-source-follower-output \
  --source-rel ip/blocks/analog/wifi_80211b \
  --command /src/rf_if_source_follower_output_probe/container_probe.sh \
  --timeout 20m --cpus 4 --memory 8g \
  --copy source-follower-probe.json:wifi-if-source-follower-output-last.json
