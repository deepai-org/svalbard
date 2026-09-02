#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label pcie-distributed-clock-fanout-physical \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/distributed_clock_fanout/container_physical.sh \
  --timeout 20m --cpus 4 --memory 8g \
  --copy sampler.spice:pcie-distributed-sampler-last.spice \
  --copy sampler-lvs.spice:pcie-distributed-sampler-last.lvs.spice \
  --copy sampler.pex.spice:pcie-distributed-sampler-last.pex.spice \
  --copy capture.spice:pcie-distributed-capture-last.spice \
  --copy capture-lvs.spice:pcie-distributed-capture-last.lvs.spice \
  --copy capture.pex.spice:pcie-distributed-capture-last.pex.spice \
  --copy physical_result.json:pcie-distributed-clock-fanout-physical-last.json
