#!/bin/bash
export OMP_NUM_THREADS=1
cd /home/ubuntu/svalbard/scratch/wired_tx/s16/fe100
r(){ python3 opts.py "$1" > /dev/null; }
q(){ n=$1; v=$2; c=$3; code=$4; extra=$5
  case $c in ssp) a='"corner":"ss","pess":true,"vdd":3.15';; ss) a='"corner":"ss","vdd":3.15';; tt) a='"corner":"typical","vdd":3.30';; ff) a='"corner":"ff","vdd":3.45';; esac
  r "{\"tag\":\"Q_n${n}_cas${v}_${c}_${code}${extra:+_$extra}\",$a,\"pad_model\":\"A16\",\"vcas\":$v,\"vct\":3.6,\"ratio\":$n,\"code\":$code${extra:+,$( [ $extra = ac ] && echo '"mode":"ac"' || echo '"mode":"ac","pol":0')}}"; }
q 0.90 4.2 tt 230; q 0.90 4.2 ff 220
q 0.90 4.5 tt 225; q 0.90 4.5 ff 215
q 0.85 4.5 tt 225; q 0.85 4.5 ff 215
q 0.90 4.2 ss 255; q 0.90 4.5 ss 255
for cfg in "0.90 4.2" "0.90 4.5" "0.85 4.5" "0.80 4.5"; do set -- $cfg
  q $1 $2 ssp 255 ac; q $1 $2 ssp 255 ac0; q $1 $2 tt 225 ac; q $1 $2 tt 225 ac0; q $1 $2 ff 215 ac; q $1 $2 ff 215 ac0; done
echo ALLDONE
