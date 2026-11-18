#!/bin/bash
while kill -0 $1 2>/dev/null; do sleep 5; done
export OMP_NUM_THREADS=1
r() { [ -e STOPQ ] && return; python3 m9.py "$1" 2>&1 | tail -1 | cut -c1-400 >> q_m9.log; }
r '{"tag":"ext16_ssp_run","c":"ssp","extm":1,"enm":0,"dx_rate":1.6e9,"tstop":1.32e-7}'
r '{"tag":"idle_hi_ssp","c":"ssp","nbits":64,"enm":0,"ovp":0,"ovn":0}'
r '{"tag":"idle_mid_ssp","c":"ssp","nbits":64,"enm":0,"ovp":1,"ovn":1}'
r '{"tag":"ext05_ssp_static","c":"ssp","extm":1,"enm":0,"dx_rate":0.5e9,"stop_at":0,"static":"10110010","tstop":4.1e-7,"ic_run":false,"tstep":1e-11}'
r '{"tag":"base3b_ssp","c":"ssp","nbits":240}'
r '{"tag":"ext16_ff_run","c":"ff","extm":1,"enm":0,"dx_rate":1.6e9,"tstop":1.32e-7}'
r '{"tag":"ext_neg_ssp","c":"ssp","extm":0,"enm":0,"dx_rate":1.6e9,"stop_at":0,"static":"10110010","tstop":4e-8,"ic_run":false}'
echo finished >> q_m9.log
