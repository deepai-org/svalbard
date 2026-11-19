#!/bin/bash
# session 14 interlock, part 2: the rows of LIMITS.md on the EXTRACTED R+C mux after the fix (one simulation at a time).
cd /home/ubuntu/svalbard/scratch/wired_tx/s14/ilk; export OMP_NUM_THREADS=1
while pgrep -f "n_stop_ssp" >/dev/null; do sleep 20; done
NEW=/home/ubuntu/svalbard/scratch/wired_tx/s13/mux3/out/wtx_mux8.rc.spice
OLD=/home/ubuntu/svalbard/scratch/wired_tx/s13/ilk/mux_rc.spice
r(){ python3 ilk.py "$1" >> q2.log 2>&1; }
r "{\"tag\":\"n_neg_force_stop_ssp\",\"c\":\"ssp\",\"net\":\"ext:$NEW\",\"phases\":\"11110000\",\"tstop\":4e-7,\"tstep\":5e-11,\"force\":true}"
r "{\"tag\":\"n_mid_ff\",\"c\":\"ff\",\"net\":\"ext:$NEW\",\"phases\":\"mmmmmmmm\",\"tstop\":4e-7,\"tstep\":5e-11,\"groups\":true}"
r "{\"tag\":\"n_mid_ssp\",\"c\":\"ssp\",\"net\":\"ext:$NEW\",\"phases\":\"mmmmmmmm\",\"tstop\":4e-7,\"tstep\":5e-11,\"groups\":true}"
r "{\"tag\":\"n_res_ff\",\"c\":\"ff\",\"net\":\"ext:$NEW\",\"phases\":\"mmmmmmmm\",\"res_pp\":0.3,\"f_ring\":3e8,\"tstop\":4e-7,\"tstep\":5e-11}"
r "{\"tag\":\"n_res_ssp\",\"c\":\"ssp\",\"net\":\"ext:$NEW\",\"phases\":\"mmmmmmmm\",\"res_pp\":0.3,\"f_ring\":3e8,\"tstop\":4e-7,\"tstep\":5e-11}"
r "{\"tag\":\"n_stop_ff\",\"c\":\"ff\",\"net\":\"ext:$NEW\",\"phases\":\"11110000\",\"tstop\":4e-7,\"tstep\":5e-11}"
r "{\"tag\":\"n_all0_ssp\",\"c\":\"ssp\",\"net\":\"ext:$NEW\",\"phases\":\"00000000\",\"tstop\":4e-7,\"tstep\":5e-11}"
r "{\"tag\":\"n_all1_ssp\",\"c\":\"ssp\",\"net\":\"ext:$NEW\",\"phases\":\"11111111\",\"tstop\":4e-7,\"tstep\":5e-11}"
r "{\"tag\":\"n_stuckH3_ssp\",\"c\":\"ssp\",\"net\":\"ext:$NEW\",\"stuck\":{\"3\":\"H\"},\"tstop\":4e-7,\"tstep\":5e-11}"
r "{\"tag\":\"n_stuckL5_ff\",\"c\":\"ff\",\"net\":\"ext:$NEW\",\"stuck\":{\"5\":\"L\"},\"tstop\":4e-7,\"tstep\":5e-11}"
for n in NEW OLD; do
  f=${!n}
  r "{\"tag\":\"${n,,}_run_ffcold240\",\"c\":\"ffcold\",\"net\":\"ext:$f\",\"f_ring\":2.4e8,\"tstop\":9e-8}"
  r "{\"tag\":\"${n,,}_run_ffcold420\",\"c\":\"ffcold\",\"net\":\"ext:$f\",\"f_ring\":4.2e8,\"tstop\":6e-8}"
  r "{\"tag\":\"${n,,}_run_sshot240\",\"c\":\"sshot\",\"net\":\"ext:$f\",\"f_ring\":2.4e8,\"tstop\":9e-8}"
  r "{\"tag\":\"${n,,}_run_sshot420\",\"c\":\"sshot\",\"net\":\"ext:$f\",\"f_ring\":4.2e8,\"tstop\":6e-8}"
done
r "{\"tag\":\"n_ramp_ffhot\",\"c\":\"ffhot\",\"net\":\"ext:$NEW\",\"phases\":\"11110000\",\"stop_at\":0,\"ramp\":1.2e-5,\"tstop\":1.3e-5,\"tstep\":1e-9}"
echo finished >> q2.log
