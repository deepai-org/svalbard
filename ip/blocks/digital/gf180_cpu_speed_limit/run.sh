#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label gf180-cpu-speed-limit \
  --source-rel ip/blocks/digital/gf180_cpu_speed_limit \
  --timeout 5m --cpus 4 --memory 4g \
  --copy result.json:gf180-cpu-speed-limit-last.json
