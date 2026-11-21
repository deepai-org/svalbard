#!/bin/bash
# sequential: one simulation at a time
export OMP_NUM_THREADS=1
cd /home/ubuntu/svalbard/scratch/wired_tx/s16/fe100
g(){ python3 -c "print('%.3f,%.3f'%(0.330*$1,0.848*$1))"; }
for c in "ssp ss true 3.15" "ss ss false 3.15" "tt typical false 3.30" "ff ff false 3.45"; do
  set -- $c; G=$(g $4)
  for code in 200 215 230 245 255; do
    python3 sweep.py "{\"tag\":\"S_$1_$code\",\"corner\":\"$2\",\"pess\":$3,\"vdd\":$4,\"code\":$code,\"gate\":[$G]}"
  done
  python3 sweep.py "{\"tag\":\"S_$1_255_rail\",\"corner\":\"$2\",\"pess\":$3,\"vdd\":$4,\"code\":255,\"gate\":[0,$4]}"
  python3 sweep.py "{\"tag\":\"S_$1_255_pol0\",\"corner\":\"$2\",\"pess\":$3,\"vdd\":$4,\"code\":255,\"pol\":0,\"gate\":[$G]}"
done
G=$(g 3.15)
python3 sweep.py "{\"tag\":\"S_ssp_255_padC\",\"corner\":\"ss\",\"pess\":true,\"vdd\":3.15,\"code\":255,\"pad_model\":\"C\",\"gate\":[$G]}"
python3 sweep.py "{\"tag\":\"S_ssp_255_ct3234\",\"corner\":\"ss\",\"pess\":true,\"vdd\":3.15,\"code\":255,\"vct\":3.234,\"gate\":[$G]}"
python3 sweep.py "{\"tag\":\"S_ssp_main255_post0\",\"corner\":\"ss\",\"pess\":true,\"vdd\":3.15,\"code\":255,\"post_code\":0,\"gate\":[$G]}"
python3 anchor.py '{"tag":"A_ssp_255_pol0","corner":"ss","pess":true,"vdd":3.15,"code":255,"pol":0,"pad_model":"RT","nsym":14}'
echo ALLDONE
