#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
exec "$repo_root/scripts/run_analog_flow.sh" --label transceiver-rail-solvers \
 --source-rel projects/programmable_transceiver_platform --timeout 3m --cpus 2 --memory 4g \
 --command /src/verification/container_rail_solvers.sh \
 --copy rail-solvers.json:transceiver-rail-solvers.json \
 --copy rail-solver-artifacts.tar.gz:transceiver-rail-solver-artifacts.tar.gz
