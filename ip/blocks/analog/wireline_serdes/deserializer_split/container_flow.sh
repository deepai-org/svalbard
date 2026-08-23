#!/usr/bin/env bash
set -euo pipefail
. /src/lane/capture_stack.sh
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/deserializer_split/layout.tcl > /work/layout.log 2>&1
sak-drc.sh -m -w /work/drc /work/deserializer_split_capture.mag > /work/drc.log 2>&1
sak-lvs.sh -m -w /work/lvs -s /src/deserializer_split/deserializer_split.spice \
  -l /work/deserializer_split_capture.mag -c deserializer_split_capture > /work/lvs.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n deserializer_split_capture_pex \
  -w /work/pex /work/deserializer_split_capture.mag > /work/pex.log 2>&1
canonicalize_capture_pex /work/pex/deserializer_split_capture.pex.spice
klayout -b -r /src/deserializer_split/render_layout.py > /work/render.log 2>&1
python3 /src/deserializer_split/check_physical.py \
  --drc /work/drc/deserializer_split_capture.magic.drc/deserializer_split_capture.magic.drc.rpt \
  --lvs /work/lvs/deserializer_split_capture.magic.lvs/deserializer_split_capture.lvs.out \
  --pex /work/pex/deserializer_split_capture.pex.spice \
  --gds /work/deserializer_split_capture.gds \
  --render /work/deserializer-split-layout.png \
  --layout /src/deserializer_split/layout.tcl \
  --schematic /src/deserializer_split/deserializer_split.spice \
  --output /work/result.json
