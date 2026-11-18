#!/bin/bash
# ring tuning for the table (serial, one simulation at a time), after pid $1; results into ../s12/tune.json (ring=layout-11Nov)
while kill -0 $1 2>/dev/null; do sleep 5; done
export OMP_NUM_THREADS=1
cd /home/ubuntu/svalbard/scratch/wired_tx/s12
t() { python3 chain.py tune "{\"corner\":\"$1\",\"temp\":$2,\"vring\":$3,\"band\":0,\"f\":$4,\"pess\":$5}" 2>&1 | tail -1 | cut -c1-200 >> ../s13/q_tune.log; }
for f in 390.625e6 405e6 312.5e6 375e6 300e6 337.5e6; do
  t ss 32 2.69 $f true
  t ss 32 3.02 $f true
  t ss 32 2.69 $f false
  t ss 32 3.02 $f false
  t typical 27 2.95 $f false
  t ff 22 3.01 $f false
  t sf 27 2.75 $f false
  t fs 27 2.75 $f false
done
echo finished >> ../s13/q_tune.log
