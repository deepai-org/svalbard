#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label wifi-if-driver-device-speed \
  --source-rel ip/blocks/analog/wifi_80211b \
  --command /src/rf_if_driver_device_screen/container_probe.sh \
  --timeout 20m --cpus 4 --memory 8g \
  --copy device-speed-probe.json:wifi-if-driver-device-speed-last.json
