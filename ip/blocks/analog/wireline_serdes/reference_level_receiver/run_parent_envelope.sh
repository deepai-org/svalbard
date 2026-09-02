#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-reference-level-receiver-parent-envelope \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/reference_level_receiver/container_parent_envelope.sh \
  --timeout 15m --cpus 2 --memory 4g \
  --copy parent-envelope.json:serdes-reference-level-receiver-parent-envelope-last.json
