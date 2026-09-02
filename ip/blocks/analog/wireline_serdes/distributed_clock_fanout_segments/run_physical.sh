#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
args=(
  --label pcie-distributed-clock-segments-physical
  --source-rel ip/blocks/analog/wireline_serdes
  --command /src/distributed_clock_fanout_segments/container_physical.sh
  --timeout 25m --cpus 4 --memory 8g
  --copy physical_result.json:pcie-distributed-clock-segments-physical-last.json
)
for kind in sampler_pre sampler_final capture_pre capture_final; do
  args+=(--copy "$kind.spice:pcie-$kind-last.spice")
  args+=(--copy "$kind.pex.spice:pcie-$kind-last.pex.spice")
  args+=(--copy "$kind-layout.tcl:pcie-$kind-last.layout.tcl")
  args+=(--copy "distributed_${kind}.mag:pcie-$kind-last.mag")
done
exec "$repo_root/scripts/run_analog_flow.sh" "${args[@]}"
