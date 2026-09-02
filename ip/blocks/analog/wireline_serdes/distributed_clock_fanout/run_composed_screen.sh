#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label pcie-distributed-clock-fanout-composed \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/distributed_clock_fanout/container_composed_screen.sh \
  --timeout 30m --cpus 4 --memory 10g \
  --copy distributed_fanout.pex.spice:pcie-distributed-fanout-last.pex.spice \
  --copy distributed_fanout_physical.json:pcie-distributed-fanout-last.physical.json \
  --copy composed_result.json:pcie-distributed-fanout-composed-last.json
