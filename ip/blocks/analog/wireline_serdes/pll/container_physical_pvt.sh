#!/usr/bin/env bash
set -euo pipefail
export RUN_VCO_PVT=1
exec /src/container_physical.sh
