#!/bin/bash
# pex.sh <name> <variant: fillm|nofill> <FRAME top>  -> out/pex/<name>.<variant>.flat.spice  (Magic 8.3.623, flat, cthresh 0)
H=/home/ubuntu/svalbard/scratch/integration/signoff-gap/fill
W=$H/out/pex/$1.$2; rm -rf $W; mkdir -p $W; cp $H/out/$1.$2.gds $W/in.gds
cat > $W/x.tcl <<T
crashbackups stop
gds read in.gds
load $3
select top cell
extract do local
extract all
ext2spice cthresh 0
ext2spice rthresh 0
ext2spice subcircuit top off
ext2spice scale off
ext2spice -o flat.spice
quit -noprompt
T
( time docker run --rm --network none --cpus 1 --memory 24g --user 1000:1000 -e HOME=/tmp --mount type=bind,src=$W,dst=/work -w /work \
  --entrypoint /bin/sh svalbard/librelane-gf180-canary:2026.08 -c 'magic -dnull -noconsole -rcfile /pdk/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc /work/x.tcl' ) > $W/magic.log 2>&1
mv $W/flat.spice $H/out/pex/$1.$2.flat.spice 2>/dev/null; tail -4 $W/magic.log > $H/out/pex/$1.$2.time; rm -rf $W
ls -la $H/out/pex/$1.$2.flat.spice
