#!/bin/bash
export OMP_NUM_THREADS=1
cd /home/ubuntu/svalbard/scratch/wired_tx/s16/fe100
C=("ssp ss true 3.15" "ss ss false 3.15" "tt typical false 3.30" "ff ff false 3.45")
r(){ python3 opts.py "$1"; }
for c in "${C[@]}"; do set -- $c
  r "{\"tag\":\"O_base_$1\",\"corner\":\"$2\",\"pess\":$3,\"vdd\":$4}"
  for v in 4.0 4.5 5.0; do r "{\"tag\":\"O_cas${v}_$1\",\"corner\":\"$2\",\"pess\":$3,\"vdd\":$4,\"vcas\":$v}"; done
  for k in 1.5 2.0; do r "{\"tag\":\"O_w${k}_$1\",\"corner\":\"$2\",\"pess\":$3,\"vdd\":$4,\"wscale\":$k}"; done
  for n in 0.65 0.70 0.75; do r "{\"tag\":\"O_n${n}_$1\",\"corner\":\"$2\",\"pess\":$3,\"vdd\":$4,\"ratio\":$n}"; done
  for ct in 4.0 4.5 5.0; do r "{\"tag\":\"O_ct${ct}_$1\",\"corner\":\"$2\",\"pess\":$3,\"vdd\":$4,\"vct\":$ct}"; done
done
for c in "${C[@]:0:1}" "${C[@]:3:1}"; do set -- $c
  r "{\"tag\":\"O_cas5.0_$1_200\",\"corner\":\"$2\",\"pess\":$3,\"vdd\":$4,\"vcas\":5.0,\"code\":200}"
  r "{\"tag\":\"O_w2.0_$1_200\",\"corner\":\"$2\",\"pess\":$3,\"vdd\":$4,\"wscale\":2.0,\"code\":200}"
done
echo ALLDONE
