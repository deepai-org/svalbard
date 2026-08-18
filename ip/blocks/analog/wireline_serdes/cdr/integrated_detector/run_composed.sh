#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label cdr-composed-error \
  --source-rel ip/blocks/analog/wireline_serdes/cdr \
  --timeout 90m --cpus 4 --memory 8g \
  --command /src/integrated_detector/container_composed_extracted.sh \
  --copy composed-summary.json:cdr-composed-error-last.json \
  --copy composed-result.json:cdr-composed-error-cases-last.json \
  --copy extracted-calibration.json:cdr-composed-error-calibration-last.json \
  --copy schematic-error-calibration.json:cdr-composed-error-schematic-last.json
