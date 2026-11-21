#!/bin/bash
export OMP_NUM_THREADS=1
cd /home/ubuntu/svalbard/scratch/wired_tx/s16/fe100
r(){ python3 opts.py "$1" > /dev/null; }
q(){ n=$1; v=$2; c=$3; code=$4; extra=$5
  case $c in ssp) a='"corner":"ss","pess":true,"vdd":3.15';; ss) a='"corner":"ss","vdd":3.15';; tt) a='"corner":"typical","vdd":3.30';; ff) a='"corner":"ff","vdd":3.45';; esac
  r "{\"tag\":\"Q_n${n}_cas${v}_${c}_${code}${extra:+_$extra}\",$a,\"pad_model\":\"A16\",\"vcas\":$v,\"vct\":3.6,\"ratio\":$n,\"code\":$code${extra:+,$( [ $extra = ac ] && echo '"mode":"ac"' || echo '"mode":"ac","pol":0')}}"; }
q 0.90 4.2 tt 205; q 0.90 4.2 ff 195
q 0.90 4.5 tt 205; q 0.90 4.5 ff 195
q 0.85 4.5 tt 195; q 0.85 4.5 ff 185
echo ALLDONE
