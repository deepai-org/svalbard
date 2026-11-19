#!/bin/bash
# runj.sh JOBFILE : 3 parallel lanes through the wired_rx slot.sh
cd "$(dirname "$0")"; export OMP_NUM_THREADS=1
xargs -P 3 -I{} bash -c '/home/ubuntu/svalbard/scratch/wired_rx/slot.sh bash -c "{}" >> '"$1"'.log 2>&1' < "$1"
