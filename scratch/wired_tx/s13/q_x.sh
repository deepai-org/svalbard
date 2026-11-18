#!/bin/bash
# extracted revision-3 mux (C-only) checks, one at a time
export OMP_NUM_THREADS=1
E=/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/wired_tx/generated/fast/wtx_mux8.ext.spice
r() { [ -e STOPQ ] && return; python3 m9.py "$1" 2>&1 | tail -1 | cut -c1-400 >> q_x.log; }
r '{"tag":"x3_base_ssp","c":"ssp","nbits":240,"ext":"'$E'","probes":["xmux.DN0","xmux.DN3"]}'
r '{"tag":"x3_start_ssp405","c":"ssp","rate":3.24e9,"nbits":320,"ext":"'$E'","ic_run":false,"pad":false}'
r '{"tag":"x3_start_ffhot240","c":"ffhot","rate":1.92e9,"nbits":200,"ext":"'$E'","ic_run":false,"pad":false}'
r '{"tag":"x3_start_sshot405","c":"sshot","rate":3.24e9,"nbits":320,"ext":"'$E'","ic_run":false,"pad":false}'
echo finished >> q_x.log
