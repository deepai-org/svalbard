#!/bin/bash
# runs after the first ssp list (same simulation slot): waits for its python to exit
while kill -0 $1 2>/dev/null; do sleep 5; done
export OMP_NUM_THREADS=1
python3 bath.py ff 2.4e9 -0.2 -0.1 0.0 0.1 0.2 0.3 0.4 0.5 0.6 -0.4 > bath_ff24.out 2>&1
python3 bath.py ff 3.24e9 -0.2 -0.1 0.0 0.1 0.2 0.3 0.4 > bath_ff324.out 2>&1
python3 bath.py ssp 3.125e9 -0.1 -0.2 -0.3 0.5 > bath_ssp2.out 2>&1
echo done > q2.done
