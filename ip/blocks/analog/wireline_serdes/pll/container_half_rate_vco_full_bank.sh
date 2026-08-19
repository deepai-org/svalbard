#!/usr/bin/env bash
set -euo pipefail
export SPLIT_ENVIRONMENT_SET=full
exec /src/pll/container_split_control_vco.sh
