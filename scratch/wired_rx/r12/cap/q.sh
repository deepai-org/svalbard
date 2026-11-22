#!/bin/bash
# usage: q.sh NAME NETLIST "tag args..." ...   one slot.sh job per case; log qNAME.log; skips tags whose res/TAG.json exists
cd /home/ubuntu/svalbard/scratch/wired_rx/r12/cap
n=$1; net=$2; shift 2
for spec in "$@"; do
  set -- $spec; tag=$1; shift
  [ -f res/$tag.json ] && continue
  ../../slot.sh python3 run7f.py $tag $net hop/reg_r7f.json "$@" >> q$n.log 2>&1
done
echo ALL >> q$n.log
