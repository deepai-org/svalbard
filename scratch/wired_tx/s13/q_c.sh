#!/bin/bash
# real-chain engineering checks (schematic mux + aux, extracted wtx_ser8d), one at a time, after pid $1
while kill -0 $1 2>/dev/null; do sleep 5; done
export OMP_NUM_THREADS=1
r() { [ -e STOPQ ] && return; python3 chain13.py "$1" 2>&1 | tail -1 | cut -c1-400 >> q_c.log; }
r '{"tag":"c2_idle0_ss","rate":3.125e9,"corner":"ss","temp":32,"vdd":3.15,"vring":2.69,"nwords":14,"idle":[[0,0],[1.0e-7,1],[1.26e-7,0]],"idle_mode":0,"keep":true}'
r '{"tag":"c3_usb_ss","rate":2.4e9,"n_over":5,"tap":1,"main_code":0,"corner":"ss","temp":32,"vdd":3.15,"vring":2.69,"keep":true}'
r '{"tag":"c4_idle1_ss","rate":3.125e9,"corner":"ss","temp":32,"vdd":3.15,"vring":2.69,"nwords":14,"idle":[[0,0],[1.0e-7,1],[1.26e-7,0]],"idle_mode":1,"keep":true}'
echo finished >> q_c.log
