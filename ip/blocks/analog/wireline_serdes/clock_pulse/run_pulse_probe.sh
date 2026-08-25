#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-clock-pulse-probe \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/clock_pulse/container_pulse_probe.sh \
  --timeout 5m --cpus 2 --memory 4g \
  --copy pulse-probe-result.json:clock-pulse-probe-last.json
