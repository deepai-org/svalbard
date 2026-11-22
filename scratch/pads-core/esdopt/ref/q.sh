#!/bin/bash
# evidence queue (ONE simulation / heavy job at a time, sequential). usage: q.sh <build>   progress: q-<build>.progress
cd /home/ubuntu/svalbard/scratch/pads-core/esdopt/ref; export OMP_NUM_THREADS=1; n=$1; P=q-$n.progress; : > $P
st(){ echo "== $1 $(date -u +%H:%M:%S)" >> $P; }
PUBG=projects/programmable_transceiver_platform/analog/pads/generated/stress-safe-families/reference
RING="--ringv 0.155,0.189,0.46,0.57 --far 5,7 --sitecap 1n,0.7 --cur"
st R; ./rflow.sh esdopt/ref/build/$n/pad/combined.gds tx_with_primary r_$n site >> $P
for c in typ high; do python3 mkmodel.py build/$n/pad/physical.spice r_$n $c models/${n}_r_$c.spice 1 >> $P 2>&1; done
python3 mkmodel.py build/$n/pad/physical.spice r_$n typ models/${n}_zero.spice 0.01 >> $P 2>&1
for c in typ high; do python3 mkrail.py models/${n}_r_$c.spice checks/$n/asm_flat.spice build/$n/pad/physical.spice models/${n}_r_${c}_rail.spice >> $P 2>&1; done
st esd-toy; python3 esd_ref.py x toy --toy 2 --cases P+VSS --kv 2 --cdm 2 $RING > logs/esd-toy.log 2>&1
st esd-negative; python3 esd_ref.py models/${n}_r_high.spice ${n}rh_nosite --strip-site --cases P+VSS,P+N --kv 2 --cdm 2 $RING > logs/$n-esd-nosite.log 2>&1
st esd-high; python3 esd_ref.py models/${n}_r_high.spice ${n}rh --kv 2,1 --cdm 1,2,3 $RING > logs/$n-esd-high.log 2>&1
st esd-typ; python3 esd_ref.py models/${n}_r_typ.spice ${n}rt --kv 2 --cdm 2 $RING > logs/$n-esd-typ.log 2>&1
rm -f esdrun/*.spice esdrun/*.log esdrun/*.dat
st padc; python3 padc_ref.py models/${n}_r_typ_rail.spice ${n}rt_rail > logs/$n-padc.log 2>&1
python3 padc_ref.py models/${n}_r_high_rail.spice ${n}rh_rail >> logs/$n-padc.log 2>&1
python3 padc_ref.py models/${n}_r_typ_rail.spice ${n}rt_rail_ctest --ctest 100f >> logs/$n-padc.log 2>&1
rm -rf benchrun/*
st done
