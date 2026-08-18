#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label cdr-sampler \
  --source-rel ip/blocks/analog/wireline_serdes/cdr \
  --timeout 300m --cpus 2 --memory 4g \
  --copy result.json:cdr-sampler-last.json \
  --copy cdr_sampler-layout.png:cdr-sampler-layout-last.png
