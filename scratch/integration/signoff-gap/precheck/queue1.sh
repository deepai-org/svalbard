#!/bin/bash
# sequential queue (one heavy job at a time)
cd /home/ubuntu/svalbard/scratch/integration/signoff-gap/precheck
A=/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog
T=/home/ubuntu/svalbard/scratch/chip-assembly-dev/pt_chip_top.gds
./native_kl.sh $A/timing/generated/aosc.gds pt_aosc antenna aosc_ant_proj_kl307 proj kl307
./native_kl.sh $T pt_chip_top antenna top_ant_proj_kl307_w1 proj kl307 2 1
./native_kl.sh $T pt_chip_top antenna top_ant_proj_kl307_w4 proj kl307 1 4
./native_kl.sh $T pt_chip_top antenna top_ant_live_kl309_w1 live kl309 2 1
./native_kl.sh $T pt_chip_top antenna top_ant_proj_kl309_w4 proj kl309 1 4
while read n g t; do
  for d in main antenna; do
    [ $d = main ] && D='all,-antenna,-density,-cup' || D=antenna
    ./native_kl.sh $A/$g $t "$D" blk_${n}_${d}_live_kl309 live kl309
  done
done <<L
pll_ring timing/generated/pll_ring.gds pt_pll_ring
qvco timing/generated/lcvco/pt_lc_qvco5.gds pt_lc_qvco5
lna rf_rx/generated/lna.gds pt_lna
adc_i converters/generated/adc_i.gds pt_adc_i
pad_rf_pair pads/generated/stress-safe-families/rf-pair/pad.gds pad_rf_pair
wiredtx wired_tx/generated/wiredtx.gds pt_wiredtx
L
./native_kl.sh $T pt_chip_top comp,contact top_compcontact_proj_kl309 proj kl309 2 1
./native_kl.sh $T pt_chip_top comp,contact top_compcontact_live_kl309 live kl309 2 1
echo QDONE
