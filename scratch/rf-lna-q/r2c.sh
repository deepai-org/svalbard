#!/bin/bash
# round-2 transients on the final layout: 2 slots (HBM screen first, then start-up || chain, then IIP3)
export OMP_NUM_THREADS=1
RX=/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/rf_rx
(cd /home/ubuntu/svalbard/scratch/rf-rx-r2b && python3 hbm_lna.py base pos_ss pos_tt pos_ff neg_ss > /home/ubuntu/svalbard/scratch/rf-lna-q/hbm_L8.log 2>&1; python3 hbm_lna.py neg pos_ss >> /home/ubuntu/svalbard/scratch/rf-lna-q/hbm_L8.log 2>&1
 cd $RX && NSTART=2 JOBS=1 python3 lna_close.py startup > /home/ubuntu/svalbard/scratch/rf-lna-q/r2c_startup.log 2>&1; rm -f /home/ubuntu/svalbard/scratch/rf_rx/close/startup/*.txt
 mkdir -p /home/ubuntu/svalbard/scratch/rf-lna-q/lin && cd /home/ubuntu/svalbard/scratch/rf-lna-q/lin && python3 $RX/linearity.py iip3 -30 > ../iip3.log 2>&1) &
(cd $RX && JOBS=1 python3 lna_close.py chain > /home/ubuntu/svalbard/scratch/rf-lna-q/r2c_chain.log 2>&1) &
wait; echo ALLDONE
