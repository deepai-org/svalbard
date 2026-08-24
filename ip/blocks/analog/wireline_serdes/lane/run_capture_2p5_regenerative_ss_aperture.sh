#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-lane-capture-2p5-regenerative-ss-aperture \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/lane/container_capture_2p5_regenerative_ss_aperture.sh \
  --timeout 90m --cpus 2 --memory 10g \
  --copy ss-regenerative-aperture.json:ss-regenerative-aperture-last.json
