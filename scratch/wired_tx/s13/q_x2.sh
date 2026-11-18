#!/bin/bash
while pgrep -x -f "/bin/bash ./q_x.sh" > /dev/null; do sleep 5; done
export OMP_NUM_THREADS=1
E=/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/wired_tx/generated/fast/wtx_mux8.ext.spice
python3 cal.py '{"tag":"calx_ssp_ideal","c":"ssp","iters":2,"pad":false,"ext":"'$E'"}' > calx_ssp_ideal.out 2>&1
CODES=$(python3 -c "import json;print(json.load(open('calres/calx_ssp_ideal.json'))['final_codes'])")
python3 m9.py '{"tag":"x3_cal_ssp","c":"ssp","nbits":240,"ext":"'$E'","codes":'"$CODES"'}' 2>&1 | tail -1 | cut -c1-400 >> q_x.log
echo finished2 >> q_x.log
