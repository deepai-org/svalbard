#!/bin/bash
# mkext.sh <cell dir under ext/> <cell> <tag> <extresist option lines separated by ;>   one Magic extresist run (call through ../../slot.sh)
# Magic 8.3.678 of the pinned analog image (same image as wrx_flow.ANALOG_IMAGE), gf180mcuD tech of that image.
set -e
H=/home/ubuntu/svalbard/scratch/wired_rx/r12/ctle
d=$H/ext/$1; cell=$2; tag=$3; opts=$(echo "$4" | tr ';' '\n')
rm -f $d/$cell.ext $d/$cell.res.ext $d/$cell.sim $d/$cell.nodes
cat > $d/rc.tcl <<EOT
crashbackups stop
load $cell
select top cell
extract all
ext2sim labels on
ext2sim
$opts
extresist all
ext2spice lvs
ext2spice cthresh 0
ext2spice rthresh 0
ext2spice extresist on
ext2spice -o $cell.$tag.raw.spice
quit -noprompt
EOT
cat > $d/rc.sh <<'EOT'
export PDK_ROOT=/foss/pdks PDK=gf180mcuD
/foss/tools/bin/magic -dnull -noconsole -rcfile /foss/pdks/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc rc.tcl > rc.log 2>&1
EOT
docker run --rm --network none --cpus 1 --memory 6g -e OMP_NUM_THREADS=1 --user "$(id -u):$(id -g)" -e HOME=/tmp --entrypoint /bin/bash \
  --mount type=bind,src=$d,dst=/work -w /work sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305 /work/rc.sh
cp $d/rc.log $d/rc.$tag.log; cp $d/rc.tcl $d/rc.$tag.tcl
echo "$tag: $(grep -c '^R' $d/$cell.$tag.raw.spice) R; $(tail -3 $d/rc.log | tr '\n' ' ')"
