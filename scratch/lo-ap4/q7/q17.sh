#!/bin/bash
# r9 range runs: RF cell rft9f (MIM 9.0), core-top C topc9f.json, loads r9; <= 3 envq at once
cd /home/ubuntu/svalbard/scratch/lo-ap4/q7; export OMP_NUM_THREADS=1 QRFW=/home/ubuntu/svalbard/scratch/lo/r4_qvco2/rft9f QTOPC=topc9g.json SPIRAL_SPICE=/home/ubuntu/svalbard/scratch/lo-ap4/sp290/spiral.spice
while read c; do
  while [ $(pgrep -u $(id -u) -f "envq.py" | wc -l) -ge 3 ]; do sleep 20; done
  nohup python3 envq.py r17 "$c" > r17/$(echo $c|tr ':,=' '___').log 2>&1 &
  sleep 5
done < q17.jobs
wait
