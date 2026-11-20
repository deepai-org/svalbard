#!/bin/sh
# session 16 last follow-up: mux (pair-C trims) + aux + block from disk, IR phase O 10.5 um, mux eye (same bench as x3_cal_ssp)
export OMP_NUM_THREADS=1
S=/home/ubuntu/svalbard/scratch/wired_tx/s13
W=/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/wired_tx
cd $W && python3 wtx_mux8_layout.py all > $S/mux3/run16.log 2>&1; echo "mux rc=$?"
python3 wtx8_aux_layout.py > $S/mux3/aux16.log 2>&1; echo "aux rc=$?"
python3 pt_wiredtx8_layout.py > $S/top/run16.log 2>&1; echo "blk rc=$?"
rm -rf $S/top/ir/phO; sh $S/top/ir/run.sh > $S/top/ir/run16.log 2>&1; echo "ir rc=$?"
cd $S && python3 m9.py '{"tag":"s16b_cal_ssp","c":"ssp","nbits":240,"ext":"'$S'/mux3/out/wtx_mux8.ext.spice","codes":[1,0,0,0,0,0,0,0]}' 2>&1 | tail -1
echo finished
