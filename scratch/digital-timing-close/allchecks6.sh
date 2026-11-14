#!/bin/bash
# r6 regression, serial (one light job at a time). Log: scratch/digital-timing-close/allchecks.r6.log
cd /home/ubuntu/svalbard; export OMP_NUM_THREADS=1
L=scratch/digital-timing-close/allchecks.r6.log; : > $L
for t in transceiver-regfile transceiver-regfile-formal transceiver-pattern transceiver-freq-count-formal transceiver-pair-word-formal transceiver-pair-gearbox-formal transceiver-chip-io transceiver-por-bypass-chip transceiver-ctl-blocks transceiver-digital-rtl-checks transceiver-clocktree-slow transceiver-clocktree-slow-formal transceiver-contract transceiver-tapeout-readiness transceiver-observation-coverage; do
  s=$(date +%s); make $t > scratch/digital-timing-close/chk6_$t.log 2>&1; rc=$?; echo "$t rc=$rc $(( $(date +%s)-s ))s" >> $L
done
echo ALLDONE >> $L
