#!/bin/bash
# frame + PDK fill + density for representative blocks (copies only). usage: blocks_fill.sh
cd /home/ubuntu/svalbard/scratch/integration/signoff-gap/fill
A=/repo/projects/programmable_transceiver_platform/analog
while read n g; do
  ./kl.sh frame.py -rd gds=$A/$g -rd out=/h/out/$n.framed.gds
  ./run_fill.sh out/$n.framed.gds $n.fill.gds 2
  ./kl.sh dens.py -rd gds=/h/out/$n.fill.gds -rd out=/h/out/$n.dens.json
  rm -f out/$n.framed.gds
done <<L
pll_ring timing/generated/pll_ring.gds
qvco timing/generated/lcvco/pt_lc_qvco5.gds
lna rf_rx/generated/lna.gds
adc_i converters/generated/adc_i.gds
pad_rf_pair pads/generated/stress-safe-families/rf-pair/pad.gds
L
echo ALLDONE
