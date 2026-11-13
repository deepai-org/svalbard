#!/bin/bash
# Native (aarch64) KLayout from the project images with a chosen deck copy.
#   native_kl.sh <gds abs> <topcell> <decks> <tag> <live|proj> <kl309|kl307> [threads=1] [workers=1]
S=/home/ubuntu/svalbard/scratch/integration/signoff-gap
[ "$5" = live ] && DECK=$S/precheck/pdk_792ef67/drc || DECK=$S/precheck/pdk_f6eeac7/drc
if [ "$6" = kl307 ]; then IMG=svalbard/librelane-gf180-canary:2026.08; SH=/bin/sh; PRE=""; else IMG=sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305; SH=/bin/bash; PRE='export PATH=$PATH:/foss/tools/klayout LD_LIBRARY_PATH=/foss/tools/klayout;'; fi
O=$S/precheck/runs/$4; mkdir -p $O
( time docker run --rm --network none --cpus ${7:-1} --memory 28g --user $(id -u):$(id -g) -e HOME=/tmp \
  -v $DECK:/deck:ro -v "$(realpath $1)":/in/in.gds:ro -v $O:/out --entrypoint $SH $IMG -c \
  "$PRE klayout -b -zz -r /deck/gf180mcu.drc -rd input=/in/in.gds -rd topcell=$2 -rd report=/out/report.lyrdb -rd decks='$3' -rd variant=gf180mcuD -rd workers=${8:-1} -rd threads=${7:-1}" ) > $O/run.log 2>&1
echo "EXIT $?" >> $O/run.log
python3 -I $S/precheck/count_lyrdb.py $O/report.lyrdb > $O/counts.json 2>/dev/null; rm -f $O/report.lyrdb
grep -E "ratio|ERROR|rdb.cc|^real|EXIT" $O/run.log | cut -c1-160 | tail -14 > $O/summary.txt
tr '\n' ' ' < $O/counts.json | cut -c1-400; echo
