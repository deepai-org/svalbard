#!/usr/bin/env bash
# LU-02 isolation-clamp family (pads owner, 2026-11-10): layout + Magic DRC + KLayout DRC + LVS + PEX of
# iso_clamp, iso_clamp_x4, iso_pd, iso_pd2 only (physical.sh in the pinned image), then the tapeout KLayout
# precheck (uniquify + kl_block_drc) per cell. Usage: iso_family.sh <outdir>
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../../.." && pwd)
PROJ="$ROOT/projects/programmable_transceiver_platform"
IMG=docker.io/hpretl/iic-osic-tools@sha256:89641950bbf247c522188629992b6271e391e38372ca0f8e3c850480874948a3
OUT="${1:?outdir}"; mkdir -p "$OUT"
CELLS="iso_clamp:logic:- iso_clamp_x4:logic:- iso_pd:logic:- iso_pd2:logic:-"
docker run --rm --network none --cpus 4 --memory 8g --user "$(id -u):$(id -g)" --env HOME=/tmp --tmpfs /tmp:size=1g,mode=1777 \
  --env PDK=gf180mcuD --env PDKPATH=/foss/pdks/gf180mcuD \
  --mount "type=bind,src=$HERE,dst=/src/analog/island_support,readonly" \
  --mount "type=bind,src=$PROJ/spec/analog-architecture.json,dst=/src/spec/analog-architecture.json,readonly" \
  --mount "type=bind,src=$OUT,dst=/work" --workdir /work --entrypoint /bin/bash "$IMG" -lc "bash /src/analog/island_support/physical.sh $CELLS" > "$OUT/physical.log" 2>&1
for c in iso_clamp iso_clamp_x4 iso_pd iso_pd2; do
  python3 -c "import sys; sys.path.insert(0, '$PROJ/analog'); import gds_uniquify as g, json; \
print(json.dumps(g.publish_checked('$OUT/layout/$c.gds', '$c', '$c')))" > "$OUT/layout/$c-kldrc.log" 2>&1 || true
done
echo ISO_DONE
