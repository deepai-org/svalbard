#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label wifi-2p4g-lna-external-lo-mixer-parent \
  --source-rel ip/blocks/analog/wifi_80211b \
  --command /src/rf_rx_external_lo_parent/container_parent_physical.sh \
  --timeout 45m --cpus 2 --memory 10g \
  --copy parent-physical-smoke.json:wifi-rx-parent-physical-smoke-last.json \
  --copy parent-physical-result.json:wifi-rx-parent-physical-last.json \
  --copy parent-pex-result.json:wifi-rx-parent-pex-last.json \
  --copy wifi-rx-external-lo-parent-layout.png:wifi-rx-parent-layout-last.png \
  --copy wifi_rx_external_lo_parent.pex.spice:wifi-rx-parent-last.pex.spice
