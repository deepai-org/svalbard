#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label lane-rx-pi-clock-chain-ss \
  --source-rel ip/blocks/analog/wireline_serdes \
  --timeout 30m --cpus 2 --memory 10g \
  --command /src/lane_rx_pi_capture/container_clock_chain_ss.sh \
  --copy clock-chain-ss-result.json:lane-rx-pi-clock-chain-ss-result.json
