#!/bin/bash
# queue: <=3 envq processes at once (all users of this machine's LO slot); OMP 1
cd /home/ubuntu/svalbard/scratch/lo-ap4/q7; export OMP_NUM_THREADS=1
R=/home/ubuntu/svalbard/scratch/lo/r4_qvco2
while read v c; do
  while [ $(pgrep -u $(id -u) -f "envq.py" | wc -l) -ge 3 ]; do sleep 20; done
  QRFW=$R/rf$v nohup python3 envq.py r9${v#t9} "$c" > r9${v#t9}_$(echo $c|tr ':,=' '___').log 2>&1 &
  sleep 5
done < q9.jobs
wait
