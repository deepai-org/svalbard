#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label wifi-2p4g-rf-nfet-array-coupon \
  --source-rel ip/blocks/analog/wifi_80211b \
  --command /src/rf_nfet_array_coupon/container_coupon_physical.sh \
  --timeout 20m --cpus 2 --memory 8g \
  --copy coupon-physical-smoke.json:wifi-rf-nfet-array-coupon-smoke-last.json \
  --copy coupon-physical-result.json:wifi-rf-nfet-array-coupon-physical-last.json \
  --copy coupon-pex-result.json:wifi-rf-nfet-array-coupon-pex-last.json \
  --copy wifi-rf-nfet-array-coupon-layout.png:wifi-rf-nfet-array-coupon-layout-last.png \
  --copy wifi_rf_nfet_array_coupon.pex.spice:wifi-rf-nfet-array-coupon-last.pex.spice
