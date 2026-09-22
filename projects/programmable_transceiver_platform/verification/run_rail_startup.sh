#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
exec "$repo_root/scripts/run_analog_flow.sh" --label transceiver-rail-startup \
 --source-rel projects/programmable_transceiver_platform --timeout 2m --cpus 2 --memory 4g \
 --command /src/verification/container_rail_startup.sh \
 --copy rail-startup.json:transceiver-rail-startup.json \
 --copy rail-startup-artifacts.tar.gz:transceiver-rail-startup-artifacts.tar.gz
