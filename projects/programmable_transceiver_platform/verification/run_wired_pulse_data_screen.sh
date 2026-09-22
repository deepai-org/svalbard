#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
OUT="$ROOT/scratch/transceiver-wired-pulse-data-gf180"
mkdir -p "$OUT"
docker run --rm --platform linux/arm64 --network none --cpus 2 --memory 8g \
 --env PDK=gf180mcuD --env PDKPATH=/foss/pdks/gf180mcuD --entrypoint /bin/bash \
 -v "$ROOT/ip/blocks/analog/wireline_serdes:/src:ro" \
 -v "$ROOT/projects/programmable_transceiver_platform/analog:/screen:ro" \
 -v "$OUT:/work" --workdir /work \
 sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305 \
 -lc '/src/clock_pulse/container_pulse_extract.sh &&
 python3 /src/pulse_bridge_lane/check_pulse_extract.py \
 --drc-log /work/drc-stage.log --lvs-log /work/lvs-stage.log \
 --pex /work/pex/clock_pulse_generator.pex.spice \
 --schematic /src/clock_pulse/clock_pulse_generator.spice \
 --layout-generator /src/clock_pulse/generate_pulse_layout.py \
 --output /work/pulse-physical.json &&
 python3 /screen/wired_pulse_data_screen.py'
