#!/bin/bash
export OMP_NUM_THREADS=1
cd /home/ubuntu/svalbard/scratch/wired_tx/s16/fe100
C=("ssp ss true 3.15" "ss ss false 3.15" "tt typical false 3.30" "ff ff false 3.45")
r(){ python3 opts.py "$1"; }
for c in "${C[@]}"; do set -- $c
  for k in 1.5 2.0; do r "{\"tag\":\"O_w${k}_$1\",\"corner\":\"$2\",\"pess\":$3,\"vdd\":$4,\"wscale\":$k}"; done
  r "{\"tag\":\"O_w2.0_cas4.5_$1\",\"corner\":\"$2\",\"pess\":$3,\"vdd\":$4,\"wscale\":2.0,\"vcas\":4.5}"
  r "{\"tag\":\"O_w2.0_ct4.5_$1\",\"corner\":\"$2\",\"pess\":$3,\"vdd\":$4,\"wscale\":2.0,\"vct\":4.5}"
  r "{\"tag\":\"O_w2.0_cas4.5_ct4.5_$1\",\"corner\":\"$2\",\"pess\":$3,\"vdd\":$4,\"wscale\":2.0,\"vcas\":4.5,\"vct\":4.5}"
  r "{\"tag\":\"O_cas5.0_ct4.5_$1\",\"corner\":\"$2\",\"pess\":$3,\"vdd\":$4,\"vcas\":5.0,\"vct\":4.5}"
done
r '{"tag":"O_w2.0_ssp_200","corner":"ss","pess":true,"vdd":3.15,"wscale":2.0,"code":200}'
for o in '"wscale":2.0,"vcas":4.5,"vct":4.5' '"vcas":5.0,"vct":4.5'; do
  t=$(echo $o | tr -d '":,'); r "{\"tag\":\"O_ac_${t}\",\"corner\":\"typical\",\"vdd\":3.3,\"mode\":\"ac\",$o}"
done
echo ALLDONE
