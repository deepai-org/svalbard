#!/usr/bin/env bash
set -euo pipefail

source /src/pll/container_vco_band_physical.sh

magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/pll/selector_unit_layout.tcl > /work/vco-band-selector-layout.log 2>&1
sak-drc.sh -m -w /work/vco-band-selector-drc /work/vco_selector_unit.mag \
  > /work/vco-band-selector-drc-stage.log 2>&1
sak-lvs.sh -m -w /work/vco-band-selector-lvs -s /src/pll/selector_unit.spice \
  -l /work/vco_selector_unit.mag -c vco_selector_unit \
  > /work/vco-band-selector-lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n vco_selector_unit_pex \
  -w /work/vco-band-selector-pex /work/vco_selector_unit.mag \
  > /work/vco-band-selector-pex-stage.log 2>&1
cp /work/vco-band-selector-drc/vco_selector_unit.magic.drc/vco_selector_unit.magic.drc.rpt \
  /work/vco-band-selector-drc.rpt
cp /work/vco-band-selector-lvs/vco_selector_unit.magic.lvs/vco_selector_unit.lvs.out \
  /work/vco-band-selector-lvs.out
cp /work/vco-band-selector-pex/vco_selector_unit.pex.spice \
  /work/vco-selector-unit.pex.spice

python3 /src/pll/run_vco_band.py --source /src/pll \
  --band-pex /work/cml-vco-band.pex.spice \
  --selector-pex /work/vco-selector-unit.pex.spice \
  --work /work/vco-band-sim --output /work/vco-band-simulation-result.json
python3 /src/pll/check_vco_band.py \
  --physical /work/vco-band-physical-result.json \
  --simulation /work/vco-band-simulation-result.json \
  --band-pex /work/cml-vco-band.pex.spice \
  --selector-drc /work/vco-band-selector-drc.rpt \
  --selector-lvs /work/vco-band-selector-lvs.out \
  --selector-pex /work/vco-selector-unit.pex.spice \
  --output /work/vco-band-result.json
