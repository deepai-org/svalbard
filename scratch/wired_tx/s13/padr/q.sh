#!/bin/bash
while kill -0 $1 2>/dev/null; do sleep 5; done
export OMP_NUM_THREADS=1
cd /home/ubuntu/svalbard/scratch/wired_tx/s13/padr
python3 padr.py A > A.out 2>&1
python3 padr.py B > B.out 2>&1
