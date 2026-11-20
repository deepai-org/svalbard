#!/bin/sh
# session 16 follow-ups: block rebuild (header bridge EM), IR phase O with 10.5 um grid-strap contacts, mux eye with matched bus C
export OMP_NUM_THREADS=1
S=/home/ubuntu/svalbard/scratch/wired_tx/s13
cd /home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/wired_tx && python3 pt_wiredtx8_layout.py > $S/top/run16.log 2>&1; echo "blk rc=$?"
rm -rf $S/top/ir/phE $S/top/ir/phO; sh $S/top/ir/run.sh > $S/top/ir/run16.log 2>&1; echo "ir rc=$?"
cd $S && python3 m9.py '{"tag":"s16_matched_ssp","c":"ssp","nbits":240,"ext":"'$S'/padr/mux16_matched.ext.spice","codes":[1,0,0,0,0,0,0,0]}' 2>&1 | tail -1
echo finished
