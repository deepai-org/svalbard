#!/bin/bash
# Die-fit packing runs, strictly one after another, one thread. usage: runset.sh <name> [env...]
cd "$(dirname "$0")"; export OMP_NUM_THREADS=1
n=$1; shift
env "$@" TAG=$n nice -n 10 python3 fit.py > run/$n.log 2>&1; echo "$n rc=$?" >> run/runset.status
