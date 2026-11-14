#!/bin/bash
# go_r7.sh <name> [stages...]: full hardening flow of the current tree into scratch/digital-timing-close/<name>
# (LibreLane tag = upper-case name). Default stage: pnr. 4 CPUs (LOAD RULE: OpenROAD/STA threads <= 4 total).
cd /home/ubuntu/svalbard
N=$1; shift; ST="${@:-pnr}"
S=scratch/digital-timing-close/$N.status
echo "start $ST $(date)" >> $S
OUT=/home/ubuntu/svalbard/scratch/digital-timing-close/$N TAG=${N^^} SVALBARD_DIGITAL_IMAGE=svalbard/librelane-gf180-guarded:2026.11 CPUS=4 MEM=20g \
  bash projects/programmable_transceiver_platform/verification/run_digital_hardening.sh $ST > scratch/digital-timing-close/$N.out 2>&1
echo "$ST rc=$? $(date)" >> $S
