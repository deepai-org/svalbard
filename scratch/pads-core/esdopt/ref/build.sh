#!/bin/bash
# usage: build.sh <name> <network dir name> [--esd-a[=JSON]]   (ONE job at a time; Magic/KLayout only) reference_clock family
cd /home/ubuntu/svalbard
export SVALBARD_PAD_IMAGE=sha256:b60278092f08c0a42fa93ed640d15d84eec53d7799790962781157ec34ceff43 OMP_NUM_THREADS=1 SVALBARD_MAGIC_TIMEOUT_S=3600
P=$PWD/projects/programmable_transceiver_platform/analog/pads; B=$PWD/scratch/pads-core/esdopt/ref/build; n=$1; net=$2; shift 2
[ -d $B/$n ] && docker run --rm --network none --entrypoint rm --mount type=bind,src=$B,dst=/work $SVALBARD_PAD_IMAGE -rf /work/$n
python3 $P/stress_safe_compact_layout.py reference_clock $B/$n $P/generated/stress-safe-families/$net "$@" > $B/$n.log 2>&1
echo "rc=$?" | tee $B/$n.done
