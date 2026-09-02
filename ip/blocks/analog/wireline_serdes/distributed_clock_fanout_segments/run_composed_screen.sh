#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label pcie-distributed-clock-segments-composed \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/distributed_clock_fanout_segments/container_composed_screen.sh \
  --timeout 30m --cpus 4 --memory 10g \
  --copy segmented_fanout.pex.spice:pcie-segmented-fanout-last.pex.spice \
  --copy segmented_fanout_physical.json:pcie-segmented-fanout-last.physical.json \
  --copy composed_result.json:pcie-segmented-fanout-composed-last.json
