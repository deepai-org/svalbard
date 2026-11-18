#!/bin/bash
# trim calibration with the real ring (schematic mux, no pad), after pid $1; then the ring tuning queue
while pgrep -x -f "/bin/bash ./q_x2.sh" > /dev/null || pgrep -x -f "/bin/bash ./q_x.sh" > /dev/null; do sleep 5; done
export OMP_NUM_THREADS=1
c() { [ -e STOPQ ] && return; python3 cal.py "$1" > cal_$2.out 2>&1; }
c '{"tag":"cal_ss_lay","c":"ss","ring":{"vring":2.69,"vctrl":1.3241,"ver":"layout"},"iters":2,"pad":false}' ss_lay
c '{"tag":"cal_ssp_lay","c":"ssp","ring":{"vring":2.69,"vctrl":1.4823,"ver":"layout","pess":true},"iters":2,"pad":false}' ssp_lay
c '{"tag":"cal_ss_com","c":"ss","ring":{"vring":2.69,"vctrl":1.3241,"ver":"committed"},"iters":2,"pad":false}' ss_com
c '{"tag":"cal_ff_lay","c":"ff","ring":{"vring":3.01,"vctrl":0.9483,"ver":"layout"},"iters":2,"pad":false}' ff_lay
c '{"tag":"cal_tt_lay","c":"tt","ring":{"vring":2.95,"vctrl":1.1252,"ver":"layout"},"iters":2,"pad":false}' tt_lay
echo done > q_cal.done
exec ./q_tune.sh 999999999
