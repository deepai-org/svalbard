#!/bin/bash
# published pad_refpad: R extraction (PAD nets), R+C models, under-rail C, pad C (same benches as the candidate). ONE job at a time.
cd /home/ubuntu/svalbard/scratch/pads-core/esdopt/ref; export OMP_NUM_THREADS=1; P=q-pub.progress; : > $P
st(){ echo "== $1 $(date -u +%H:%M:%S)" >> $P; }
st R; ./rflow.sh esdopt/ref/pub/combined.gds pad_refpad r_pub >> $P
for c in typ high; do python3 mkmodel.py pub/physical.spice r_pub $c models/pub_r_$c.spice 1 >> $P 2>&1; done
st rail; mkdir -p rail/pub; ../../dock.sh "cd /work/esdopt/site && python3 railasm.py /work/esdopt/ref/pub/combined.gds pad_refpad /work/esdopt/ref/rail/pub/asm.gds 0 211" > rail/pub/railasm.log 2>&1
../site/railcap.sh rail/pub > rail/pub/railcap.txt 2>&1; rm -f rail/pub/asm.gds
for c in typ high; do python3 mkrail.py models/pub_r_$c.spice rail/pub/asm_flat.spice pub/physical.spice models/pub_r_${c}_rail.spice >> $P 2>&1; done
st padc; python3 padc_ref.py models/pub_r_typ_rail.spice pubrt_rail > logs/pub-padc.log 2>&1
python3 padc_ref.py models/pub_r_high_rail.spice pubrh_rail >> logs/pub-padc.log 2>&1
python3 padc_ref.py pub/physical.spice pubc > logs/pubc-padc.log 2>&1
rm -rf benchrun/*
st done
