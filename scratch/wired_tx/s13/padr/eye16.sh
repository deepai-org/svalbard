#!/bin/sh
# session 16 mux eye check on the new extracted wtx_mux8 (C-only netlist, as the x3_* runs of q_x.sh / q_x2.sh):
# calibrate the phase trims (cal.py, ideal phases), then the eye at ss pessimistic 3.125 Gb/s, pad on, nbits 240 --
# ideal phases (comparable to x3_cal_ssp, H 0.2112 V) and the extracted ring (layout, pess, cal_ssp_lay operating point).
cd /home/ubuntu/svalbard/scratch/wired_tx/s13
export OMP_NUM_THREADS=1
E=/home/ubuntu/svalbard/scratch/wired_tx/s13/mux3/out/wtx_mux8.ext.spice
python3 cal.py '{"tag":"cal16_ssp_ideal","c":"ssp","iters":2,"pad":false,"ext":"'$E'"}' > padr/cal16.out 2>&1
CODES=$(python3 -c "import json;print(json.load(open('calres/cal16_ssp_ideal.json'))['final_codes'])")
echo "codes $CODES"
python3 m9.py '{"tag":"s16_cal_ssp","c":"ssp","nbits":240,"ext":"'$E'","codes":'"$CODES"'}' 2>&1 | tail -1
python3 m9.py '{"tag":"s16_ring_ssp","c":"ssp","nbits":240,"ext":"'$E'","codes":'"$CODES"',"ring":{"vring":2.69,"vctrl":1.4823,"ver":"layout","pess":true}}' 2>&1 | tail -1
echo finished
