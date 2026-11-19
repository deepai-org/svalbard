#!/bin/bash
# schematic checks of the fixed mux (hysteresis input stage), one simulation at a time
cd /home/ubuntu/svalbard/scratch/wired_tx/s14/ilk; export OMP_NUM_THREADS=1
python3 hyst.py '{"h1":[1.0,1.8,0.5],"k":[0.45,1.1,0.5],"h2":[0.5,1.0]}' v > hyst.log 2>&1
r(){ python3 ilk.py "$1" >> q1b.log 2>&1; }
r '{"tag":"s_run_sshot420","c":"sshot","f_ring":4.2e8,"tstop":4e-7}'
r(){ python3 ilk.py "$1" >> q1b.log 2>&1; }
for c in ffcold ff ssp sshot; do
  r "{\"tag\":\"s_mid_$c\",\"c\":\"$c\",\"phases\":\"mmmmmmmm\",\"tstop\":5e-7,\"groups\":true}"
  r "{\"tag\":\"s_res_$c\",\"c\":\"$c\",\"phases\":\"mmmmmmmm\",\"res_pp\":0.3,\"f_ring\":3e8,\"tstop\":5e-7}"
done
r '{"tag":"s_run_ffcold240","c":"ffcold","f_ring":2.4e8,"tstop":4e-7}'
r '{"tag":"s_start_sshot420","c":"sshot","f_ring":4.2e8,"tstop":4e-7,"ic_run":false}'
r '{"tag":"s_start_ffcold240","c":"ffcold","f_ring":2.4e8,"tstop":4e-7,"ic_run":false}'
r '{"tag":"s_stuckH3_ssp","c":"ssp","stuck":{"3":"H"},"tstop":5e-7}'
r '{"tag":"s_stuckL5_ff","c":"ff","stuck":{"5":"L"},"tstop":5e-7}'
r '{"tag":"s_stop_ff","c":"ff","phases":"11110000","tstop":5e-7}'
r '{"tag":"s_ramp_ffhot","c":"ffhot","phases":"11110000","stop_at":0,"ramp":1.2e-5,"tstop":1.3e-5,"tstep":1e-9}'
echo finished >> q1b.log
