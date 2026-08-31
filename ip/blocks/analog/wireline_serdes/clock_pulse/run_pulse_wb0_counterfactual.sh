#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-clock-pulse-write-taper-counterfactual \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/clock_pulse/container_pulse_wb0_counterfactual.sh \
  --timeout 20m --cpus 2 --memory 8g \
  --copy pulse-wb0-counterfactual-smoke.json:clock-pulse-wb0-counterfactual-smoke-last.json \
  --copy pulse-wb0-counterfactual-report.json:clock-pulse-wb0-counterfactual-report-last.json \
  --copy pulse-wb0-counterfactual-result.json:clock-pulse-wb0-counterfactual-last.json
