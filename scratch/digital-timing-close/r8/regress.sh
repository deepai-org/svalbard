#!/bin/bash
# r8/regress.sh <tag>: the r7 regression list, serial. Log scratch/digital-timing-close/r8/regress_<tag>.log
cd /home/ubuntu/svalbard; export OMP_NUM_THREADS=1
L=scratch/digital-timing-close/r8/regress_$1.log; : > $L
for t in transceiver-regfile transceiver-regfile-formal transceiver-top-modes transceiver-chip-io transceiver-por-bypass-chip transceiver-contract transceiver-ctl-blocks transceiver-digital-rtl-checks; do
  s=$(date +%s); make $t > scratch/digital-timing-close/r8/chk_$1_$t.log 2>&1; rc=$?; echo "$t rc=$rc $(( $(date +%s)-s ))s" >> $L
done
echo ALLDONE >> $L
