#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label wifi-real-if-nmos-sample-switch \
  --source-rel ip/blocks/analog/wifi_80211b \
  --command /src/rf_if_nmos_sample_switch/container_physical.sh \
  --timeout 20m --cpus 2 --memory 8g \
  --copy sample-switch-physical-smoke.json:wifi-if-nmos-sample-switch-smoke-last.json \
  --copy sample-switch-physical-result.json:wifi-if-nmos-sample-switch-physical-last.json \
  --copy sample-switch-schematic-result.json:wifi-if-nmos-sample-switch-schematic-last.json \
  --copy sample-switch-pex-result.json:wifi-if-nmos-sample-switch-pex-last.json \
  --copy sample-switch-rejection-result.json:wifi-if-nmos-sample-switch-rejection-last.json \
  --copy wifi-if-nmos-sample-switch-layout.png:wifi-if-nmos-sample-switch-layout-last.png \
  --copy wifi_if_nmos_sample_switch.pex.spice:wifi-if-nmos-sample-switch-last.pex.spice
