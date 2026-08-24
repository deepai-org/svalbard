#!/usr/bin/env bash
set -euo pipefail

magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/cml_to_cmos/layout_fast.tcl > /work/fast-layout.log 2>&1
sak-drc.sh -m -w /work/fast-drc /work/cml_to_cmos.mag \
  > /work/fast-drc-stage.log 2>&1
sak-lvs.sh -m -w /work/fast-lvs \
  -s /src/cml_to_cmos/cml_to_cmos_fast.spice \
  -l /work/cml_to_cmos.mag -c cml_to_cmos \
  > /work/fast-lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n cml_to_cmos_pex \
  -w /work/fast-pex /work/cml_to_cmos.mag \
  > /work/fast-pex-stage.log 2>&1

pex=/work/fast-pex/cml_to_cmos.pex.spice
sed -i -E '1s/^\* PEX produced on .* using /\* PEX produced using /' "$pex"
grep -q '^\* PEX produced using ' "$pex"

python3 /src/cml_to_cmos/run_pvt.py \
  --source /src --pex "$pex" \
  --work /work/fast-extracted --output /work/fast-extracted.json --jobs 2 \
  --waveform-dir /work/fast-waves --pipeline-latency-ui 1 \
  --boost-policy calibrated --boost-fraction 1.0 \
  --eval-width-ps 550 --capture-delay-ps 430 --capture-width-ps 100 \
  --sample-delay-ps 120 \
  --timeout-s 300 \
  --case ss_2p97_p125_cm0p60_in0p20_load50 \
  --case ss_2p97_p125_cm0p80_in0p20_load50 \
  --case ff_2p97_p125_cm0p80_in0p20_load50 \
  --case ff_3p30_p27_cm0p80_in0p20_load50 \
  --case typical_3p63_p125_cm0p70_in0p20_load50 \
  --case ff_3p63_m40_cm0p60_in0p20_load50 \
  --case typical_3p30_p27_cm0p70_in0p20_load50 \
  --case ss_3p63_m40_cm0p80_in0p20_load50 \
  --case typical_2p97_m40_cm0p70_in0p20_load50 \
  --case ss_3p30_p27_cm0p60_in0p20_load50

CML_TO_CMOS_RENDER_VARIANT=fast \
  CML_TO_CMOS_RENDER_GDS=/work/cml_to_cmos.gds \
  CML_TO_CMOS_RENDER_PEX="$pex" \
  CML_TO_CMOS_RENDER_PATH=/work/cml_to_cmos-fast-layout.png \
  python3 /src/cml_to_cmos/render_layout.py > /work/fast-render.log 2>&1

python3 /src/cml_to_cmos/check_fast_physical.py \
  --drc /work/fast-drc/cml_to_cmos.magic.drc/cml_to_cmos.magic.drc.rpt \
  --lvs /work/fast-lvs/cml_to_cmos.magic.lvs/cml_to_cmos.lvs.out \
  --pex "$pex" --gds /work/cml_to_cmos.gds \
  --render /work/cml_to_cmos-fast-layout.png \
  --layout /src/cml_to_cmos/layout_fast.tcl \
  --layout-core /src/cml_to_cmos/layout.tcl \
  --schematic /src/cml_to_cmos/cml_to_cmos_fast.spice \
  --timing /work/fast-extracted.json \
  --output /work/cml_to_cmos-fast-physical.json

cp "$pex" /work/cml_to_cmos-fast.pex.spice
