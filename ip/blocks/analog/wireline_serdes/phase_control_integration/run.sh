#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label phase-control-integration --source-rel ip/blocks/analog/wireline_serdes \
 --command /src/phase_control_integration/container_flow.sh --timeout 30m --cpus 4 --memory 6g \
 --copy composed.json:phase-control-integration-last.json
