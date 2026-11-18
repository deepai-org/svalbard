#!/bin/bash
# revision-3 mux schematic checks, one simulation at a time, after the POST worker (pid $1) has ended
while kill -0 $1 2>/dev/null; do sleep 5; done
export OMP_NUM_THREADS=1
r() { python3 m9.py "$1" 2>&1 | tail -1 | cut -c1-400 >> q_m9.log; }
r '{"tag":"base3_ssp","c":"ssp","nbits":240}'
r '{"tag":"ext16_ssp_static","c":"ssp","extm":1,"enm":0,"dx_rate":1.6e9,"stop_at":0,"static":"10110010","tstop":1.32e-7,"ic_run":false}'
r '{"tag":"idle_hi_ssp","c":"ssp","nbits":64,"enm":0,"ovp":0,"ovn":0}'
r '{"tag":"idle_mid_ssp","c":"ssp","nbits":64,"enm":0,"ovp":1,"ovn":1}'
r '{"tag":"ext16_ff_run","c":"ff","extm":1,"enm":0,"dx_rate":1.6e9,"tstop":1.32e-7}'
r '{"tag":"ext_neg_ssp","c":"ssp","extm":0,"enm":0,"dx_rate":1.6e9,"stop_at":0,"static":"10110010","tstop":4e-8,"ic_run":false}'
echo finished >> q_m9.log
