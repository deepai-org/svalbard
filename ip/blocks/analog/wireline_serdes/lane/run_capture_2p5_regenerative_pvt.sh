#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
copies=(--copy regenerative-pvt.json:regenerative-pvt-last.json)
for name in tt ff_cold ff_hot ss_hot ss_passive; do
  copies+=(--copy "regenerative-${name}.json:regenerative-${name}-last.json")
done
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-lane-capture-2p5-regenerative-pvt \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/lane/container_capture_2p5_regenerative_pvt.sh \
  --timeout 120m --cpus 2 --memory 10g "${copies[@]}"
