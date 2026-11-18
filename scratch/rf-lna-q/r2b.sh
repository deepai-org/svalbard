#!/bin/bash
cd /home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/rf_rx
export OMP_NUM_THREADS=1 JOBS=1
python3 lna_close.py startup || echo STARTUP FAILED
python3 lna_close.py chain || echo CHAIN FAILED
echo ALLDONE
