#!/bin/bash
export OMP_NUM_THREADS=1
cd /home/ubuntu/svalbard/scratch/wired_tx/s16/fe100
q(){ ct=$1; n=$2; c=$3; code=$4; mode=$5
  case $c in ssp) a='"corner":"ss","pess":true,"vdd":3.15';; ss) a='"corner":"ss","vdd":3.15';; tt) a='"corner":"typical","vdd":3.30';; ff) a='"corner":"ff","vdd":3.45';; esac
  m=''; [ "$mode" = ac ] && m=',"mode":"ac"'; [ "$mode" = ac0 ] && m=',"mode":"ac","pol":0'
  python3 opts.py "{\"tag\":\"R_ct${ct}_n${n}_${c}_${code}${mode:+_$mode}\",$a,\"pad_model\":\"A16\",\"vcas\":4.2,\"vct\":$ct,\"ratio\":$n,\"code\":$code$m}" > /dev/null; }
for ct in 3.50 3.45; do for n in 0.88 0.90; do q $ct $n ssp 255; q $ct $n tt 205; q $ct $n ff 195; done; done
echo ALLDONE
