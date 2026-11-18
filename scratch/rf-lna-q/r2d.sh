#!/bin/bash
export OMP_NUM_THREADS=1
while ps aux | grep -q "linearity.p[y]"; do sleep 20; done
cd /home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/rf_rx
NSTART=2 JOBS=1 python3 lna_close.py startup > /home/ubuntu/svalbard/scratch/rf-lna-q/r2c_startup.log 2>&1
rm -f /home/ubuntu/svalbard/scratch/rf_rx/close/startup/*.txt
echo ALLDONE
