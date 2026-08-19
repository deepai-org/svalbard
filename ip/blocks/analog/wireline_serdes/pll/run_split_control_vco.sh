#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label cml-split-control-vco \
  --source-rel ip/blocks/analog/wireline_serdes \
  --timeout 35m --cpus 2 --memory 4g \
  --command /src/pll/container_split_control_vco.sh \
  --copy split-control-bank-screen.json:split-control-bank-screen.json \
  --copy split_base-control-vco-screen.json:split-control-vco-screen.json \
  --copy layout-split_base-control-vco.png:layout-split-control-vco.png \
  --copy split_fast-control-vco-screen.json:split-fast-control-vco-screen.json \
  --copy layout-split_fast-control-vco.png:layout-split-fast-control-vco.png \
  --copy split_gain-control-vco-screen.json:split-gain-control-vco-screen.json \
  --copy layout-split_gain-control-vco.png:layout-split-gain-control-vco.png
