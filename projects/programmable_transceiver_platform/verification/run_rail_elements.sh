#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
exec "$repo_root/scripts/run_analog_flow.sh" --label transceiver-rail-elements \
 --source-rel projects/programmable_transceiver_platform --timeout 3m --cpus 2 --memory 4g \
 --command /src/verification/container_rail_elements.sh \
 --copy rail-elements.json:transceiver-rail-elements.json \
 --copy rail-element-artifacts.tar.gz:transceiver-rail-element-artifacts.tar.gz
