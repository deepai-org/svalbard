#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label phase-control-dac --source-rel ip/blocks/analog/wireline_serdes/phase_control_dac \
 --timeout 20m --cpus 4 --memory 6g --copy result.json:phase-control-dac-last.json \
 --copy schematic-dc.json:phase-control-dac-schematic-last.json --copy extracted-dc.json:phase-control-dac-extracted-last.json \
 --copy settling.json:phase-control-dac-settling-last.json --copy phase_control_dac-layout.png:phase-control-dac-layout-last.png \
 --copy phase_control_dac.gds:phase-control-dac-last.gds --copy pex/phase_control_dac.pex.spice:phase-control-dac-last.pex.spice
