#!/bin/bash
export OMP_NUM_THREADS=1
cd /home/ubuntu/svalbard/scratch/wired_tx/s16/fe100
r(){ python3 opts.py "$1" > /dev/null; }
for ct in 3.6 3.45; do
for c in "ssp ss true 3.15" "ss ss false 3.15" "tt typical false 3.30" "ff ff false 3.45"; do set -- $c
  for v in 4.2 4.5 4.8; do r "{\"tag\":\"P${ct}_cas${v}_$1\",\"corner\":\"$2\",\"pess\":$3,\"vdd\":$4,\"vcas\":$v,\"vct\":$ct}"; done
  for v in 4.2 4.5; do r "{\"tag\":\"P${ct}_w2_cas${v}_$1\",\"corner\":\"$2\",\"pess\":$3,\"vdd\":$4,\"wscale\":2.0,\"vcas\":$v,\"vct\":$ct}"; done
  r "{\"tag\":\"P${ct}_w1.5_cas4.5_$1\",\"corner\":\"$2\",\"pess\":$3,\"vdd\":$4,\"wscale\":1.5,\"vcas\":4.5,\"vct\":$ct}"
done; done
echo ALLDONE
