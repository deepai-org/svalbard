#!/bin/bash
# usage: rflow.sh <gds rel. to scratch/pads-core> <top> <out dir rel. to esdopt/ref> [site]   netres spec + device map + R extraction (ONE job)
cd /home/ubuntu/svalbard/scratch/pads-core; G=$1; T=$2; R=$3; mkdir -p esdopt/ref/$R
NETS="PAD_P:1 PAD_N:1"
./dock.sh "cd /work/esdopt/ref && python3 mkspec.py /work/$G $R/spec.json $R/devmap.json $NETS > $R/mkspec.log 2>&1 && python3 fixspec.py $R/spec.json $4 && python3 /work/hsfix/netres.py --gds /work/$G --top $T --spec $R/spec.json --out $R/res.json --tech /foss/pdks/gf180mcuD/libs.tech/magic/gf180mcuD.tech > $R/netres.log 2>&1; echo rc=\$? > $R/done" > /dev/null 2>&1
cat esdopt/ref/$R/done
