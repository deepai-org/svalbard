#!/bin/bash
export OMP_NUM_THREADS=1
cd /home/ubuntu/svalbard/scratch/wired_tx/s16/fe100
C=("ssp ss true 3.15" "ss ss false 3.15" "tt typical false 3.30" "ff ff false 3.45")
r(){ python3 opts.py "$1"; }
for c in "${C[@]}"; do set -- $c
  for v in 4.0 4.5 5.0; do r "{\"tag\":\"O_cas${v}_$1\",\"corner\":\"$2\",\"pess\":$3,\"vdd\":$4,\"vcas\":$v}"; done
  for k in 1.5 2.0; do r "{\"tag\":\"O_w${k}_$1\",\"corner\":\"$2\",\"pess\":$3,\"vdd\":$4,\"wscale\":$k}"; done
  for n in 0.65 0.70 0.75; do r "{\"tag\":\"O_n${n}_$1\",\"corner\":\"$2\",\"pess\":$3,\"vdd\":$4,\"ratio\":$n}"; done
  for ct in 4.0 4.5 5.0; do r "{\"tag\":\"O_ct${ct}_$1\",\"corner\":\"$2\",\"pess\":$3,\"vdd\":$4,\"vct\":$ct}"; done
done
for c in "${C[@]:0:1}" "${C[@]:3:1}"; do set -- $c
  r "{\"tag\":\"O_cas5.0_$1_200\",\"corner\":\"$2\",\"pess\":$3,\"vdd\":$4,\"vcas\":5.0,\"code\":200}"
  r "{\"tag\":\"O_w2.0_$1_200\",\"corner\":\"$2\",\"pess\":$3,\"vdd\":$4,\"wscale\":2.0,\"code\":200}"
done
# RL at the RJ45 (tt): held -1 state at 255/255, and tails off (code 0)
for o in '"vcas":3.3' '"vcas":4.5' '"vcas":5.0' '"wscale":1.5' '"wscale":2.0' '"ratio":0.65' '"ratio":0.70' '"ratio":0.75' '"vct":4.5' '"vct":5.0'; do
  t=$(echo $o | tr -d '":'); r "{\"tag\":\"O_ac_${t}\",\"corner\":\"typical\",\"vdd\":3.3,\"mode\":\"ac\",$o}"
  r "{\"tag\":\"O_ac0_${t}\",\"corner\":\"typical\",\"vdd\":3.3,\"mode\":\"ac\",\"code\":0,$o}"
done
for k in 1.5 2.0; do python3 -c "import opts; opts.padc('O_padc_w$k',$k)"; done
echo ALLDONE
