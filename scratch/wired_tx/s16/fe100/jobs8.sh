#!/bin/bash
export OMP_NUM_THREADS=1
cd /home/ubuntu/svalbard/scratch/wired_tx/s16/fe100
r(){ python3 opts.py "$1" > /dev/null; }
for n in 0.80 0.85 0.90; do for v in 4.2 4.5; do
for c in "ssp ss true 3.15" "tt typical false 3.30" "ff ff false 3.45"; do set -- $c
  r "{\"tag\":\"Q_n${n}_cas${v}_$1\",\"corner\":\"$2\",\"pess\":$3,\"vdd\":$4,\"pad_model\":\"A16\",\"vcas\":$v,\"vct\":3.6,\"ratio\":$n}"
done; done; done
echo ALLDONE
