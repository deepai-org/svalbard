#!/bin/sh
# session 16 ser8d hop timing: ring-driven probe decks (runs/p1 = ss pessimistic 3.15 V 3.125 Gb/s, runs/p_ff) with the
# previous (3bc5ca72) and the current wtx_ser8d R+C netlist.  One simulation at a time.
cd /home/ubuntu/svalbard/scratch/wired_tx/s13/runs
export OMP_NUM_THREADS=1
for d in p16_new_ssp p16_prev_ssp p16_new_ff p16_prev_ff; do
  (cd $d && /home/ubuntu/svalbard/scratch/pad-ngspice47/ngspice-47/src/ngspice -b tb.sp > tb.sp.log 2>&1); echo "$d rc=$?"
done
echo finished
