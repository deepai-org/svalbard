#!/bin/bash
# r8/go.sh <chip> [stages...]: full hardening flow of the current tree for chip rf|wired into scratch/digital_hardening-<chip>
# (the one kept run per chip; the previous one is replaced). Default stage: pnr. CPUS (default 2): two runs at once
# stay within the 4-thread load rule.
cd /home/ubuntu/svalbard
C=$1; shift; ST="${@:-pnr}"
S=scratch/digital-timing-close/run_$C.status
echo "start $ST $(date)" >> $S
CHIP=$C TAG=${C^^} SVALBARD_DIGITAL_IMAGE=svalbard/librelane-gf180-guarded:2026.11 CPUS=${CPUS:-2} MEM=16g \
  bash projects/programmable_transceiver_platform/verification/run_digital_hardening.sh $ST > scratch/digital-timing-close/run_$C.out 2>&1
echo "$ST rc=$? $(date)" >> $S
