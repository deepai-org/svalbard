#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-reference-level-receiver-sense-polarity \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/reference_level_receiver/container_sense_polarity.sh \
  --timeout 15m --cpus 2 --memory 4g \
  --copy result.json:serdes-reference-level-receiver-sense-polarity-last.json
