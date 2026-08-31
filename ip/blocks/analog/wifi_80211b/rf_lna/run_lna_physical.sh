#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label wifi-2p4g-lna-risk-macro \
  --source-rel ip/blocks/analog/wifi_80211b \
  --command /src/rf_lna/container_lna_physical.sh \
  --timeout 20m --cpus 2 --memory 8g \
  --copy lna-physical-smoke.json:wifi-lna-physical-smoke-last.json \
  --copy lna-pex-result.json:wifi-lna-pex-last.json \
  --copy wifi-lna-cs-core-layout.png:wifi-lna-layout-last.png \
  --copy wifi_lna_cs_core.pex.spice:wifi-lna-last.pex.spice
