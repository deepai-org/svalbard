#!/bin/bash
cd /home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/rf_rx
export OMP_NUM_THREADS=1 JOBS=3
for s in "$@"; do python3 lna_close.py $s || echo "STAGE $s FAILED"; done
echo ALLDONE
