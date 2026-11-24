#!/bin/bash
# r8/go.sh <chip> [variant] [stages...]: hardening of the current tree for chip rf|wired. Without a variant the run goes to
# scratch/digital_hardening-<chip> (the kept run); with a variant name (e.g. d78) to scratch/digital_hardening-<chip>-<variant>
# with LL_OVERRIDE from scratch/digital-timing-close/r8/variants/<variant>.json (placement-noise sweep). CPUS default 2.
cd /home/ubuntu/svalbard
C=$1; shift; V=""; if [ -n "$1" ] && [ -f scratch/digital-timing-close/r8/variants/$1.json ]; then V=$1; shift; fi
ST="${@:-pnr}"; N=$C${V:+-$V}
S=scratch/digital-timing-close/run_$N.status
echo "start $ST $(date)" >> $S
OV=""; [ -n "$V" ] && OV=$(cat scratch/digital-timing-close/r8/variants/$V.json)
CHIP=$C TAG=${C^^} OUT=/home/ubuntu/svalbard/scratch/digital_hardening-$N LL_OVERRIDE="$OV" SVALBARD_DIGITAL_IMAGE=svalbard/librelane-gf180-guarded:2026.11 CPUS=${CPUS:-2} MEM=16g \
  bash projects/programmable_transceiver_platform/verification/run_digital_hardening.sh $ST > scratch/digital-timing-close/run_$N.out 2>&1
echo "$ST rc=$? $(date)" >> $S
