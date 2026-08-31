#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label wifi-2p4g-rf-ostl-coupon \
  --source-rel ip/blocks/analog/wifi_80211b \
  --command /src/rf_ostl_coupon/container_coupon_physical.sh \
  --timeout 20m --cpus 2 --memory 8g \
  --copy coupon-physical-smoke.json:wifi-rf-ostl-coupon-physical-smoke-last.json \
  --copy coupon-physical-result.json:wifi-rf-ostl-coupon-physical-last.json \
  --copy coupon-pex-result.json:wifi-rf-ostl-coupon-pex-last.json \
  --copy wifi-rf-ostl-coupon-layout.png:wifi-rf-ostl-coupon-layout-last.png \
  --copy wifi_rf_ostl_coupon.pex.spice:wifi-rf-ostl-coupon-last.pex.spice
