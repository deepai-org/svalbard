#!/bin/bash
# Interlock on the extracted R+C mux (session 14). One simulation at a time; waits for the ser8d verify.
cd /home/ubuntu/svalbard/scratch/wired_tx/s13/ilk; export OMP_NUM_THREADS=1
while pgrep -f "verify.py v" >/dev/null; do sleep 30; done
run(){ python3 run_ilk.py "$@" ext='"/home/ubuntu/svalbard/scratch/wired_tx/s13/ilk/mux_rc.spice"' >> ilk_ext.log 2>&1; }
run x_stop_ssp ssp 11110000
run x_stop_ff ff 11110000 
run x_all0_ssp ssp 00000000
run x_all1_ssp ssp 11111111
run x_mid_ssp ssp mmmmmmmm
run x_mid_ff ff mmmmmmmm
run x_neg_nointerlock ssp 11110000 interlock=false
echo finished >> ilk_ext.log
