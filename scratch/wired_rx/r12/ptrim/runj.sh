#!/bin/bash
# runj.sh JOBFILE NLANES : lanes through the wired_rx slot.sh (one job = one slot)
cd "$(dirname "$0")"; export OMP_NUM_THREADS=1
xargs -P ${2:-2} -I{} bash -c '/home/ubuntu/svalbard/scratch/wired_rx/slot.sh bash -c "{}" >> '"$1"'.log 2>&1' < "$1"
