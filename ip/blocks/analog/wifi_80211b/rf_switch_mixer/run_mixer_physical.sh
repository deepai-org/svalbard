#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label wifi-2p4g-external-lo-switch-mixer \
  --source-rel ip/blocks/analog/wifi_80211b \
  --command /src/rf_switch_mixer/container_mixer_physical.sh \
  --timeout 30m --cpus 2 --memory 10g \
  --copy mixer-physical-smoke.json:wifi-mixer-physical-smoke-last.json \
  --copy mixer-pex-result.json:wifi-mixer-pex-last.json \
  --copy wifi-rf-switch-mixer-layout.png:wifi-mixer-layout-last.png \
  --copy wifi_rf_switch_mixer.pex.spice:wifi-mixer-last.pex.spice
