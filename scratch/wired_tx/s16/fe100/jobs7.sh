#!/bin/bash
export OMP_NUM_THREADS=1
cd /home/ubuntu/svalbard/scratch/wired_tx/s16/fe100
r(){ python3 opts.py "$1" > /dev/null; }
# cfg: tagprefix wscale vcas vct ; codes per corner
run(){ p=$1; w=$2; v=$3; ct=$4; shift 4
  for cc in "$@"; do set -- ${cc//:/ }
    case $1 in ssp) a='"corner":"ss","pess":true,"vdd":3.15';; ss) a='"corner":"ss","vdd":3.15';; tt) a='"corner":"typical","vdd":3.30';; ff) a='"corner":"ff","vdd":3.45';; esac
    r "{\"tag\":\"${p}_$1_$2\",$a,\"wscale\":$w,\"vcas\":$v,\"vct\":$ct,\"code\":$2}"; done; }
run P3.6_w2_cas4.2 2.0 4.2 3.6 ssp:230 ssp:215 tt:225 tt:215 ff:220 ff:210
run P3.6_w1.5_cas4.5 1.5 4.5 3.6 ssp:240 tt:235 tt:225 ff:230 ff:220
run P3.45_w2_cas4.2 2.0 4.2 3.45 ssp:240 tt:235 tt:225 ff:235 ff:225
echo ALLDONE
