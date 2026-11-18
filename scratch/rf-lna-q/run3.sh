#!/bin/bash
# run3.sh "<cmd1>" "<cmd2>" ... : at most 3 at once, OMP_NUM_THREADS=1
export OMP_NUM_THREADS=1
printf '%s\n' "$@" | xargs -P 3 -I{} bash -c '{}'
