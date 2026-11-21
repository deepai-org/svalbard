#!/bin/bash
export OMP_NUM_THREADS=1
cd /home/ubuntu/svalbard/scratch/wired_tx/s16/fe100
r(){ python3 opts.py "$1"; }
for c in "ssp ss true 3.15" "ss ss false 3.15" "tt typical false 3.30" "ff ff false 3.45"; do set -- $c
  r "{\"tag\":\"O_cas4.5_ct4.5_$1\",\"corner\":\"$2\",\"pess\":$3,\"vdd\":$4,\"vcas\":4.5,\"vct\":4.5}"; done
for v in 4.0 4.2; do r "{\"tag\":\"O_cas${v}_ct4.5_ff\",\"corner\":\"ff\",\"vdd\":3.45,\"vcas\":$v,\"vct\":4.5}"; r "{\"tag\":\"O_cas${v}_ct4.5_tt\",\"corner\":\"typical\",\"vdd\":3.3,\"vcas\":$v,\"vct\":4.5}"; done
for code in 215 230; do for c in "tt typical 3.30" "ff ff 3.45"; do set -- $c
  r "{\"tag\":\"O_cas4.5_ct4.5_$1_$code\",\"corner\":\"$2\",\"vdd\":$3,\"vcas\":4.5,\"vct\":4.5,\"code\":$code}"; done; done
echo ALLDONE
