#!/bin/bash
# xor.sh <gds> <top> <ref gds> [ref top]  -> XOR_AREA_UM2 (KLayout in the tool container)
R=/home/ubuntu/svalbard; a=${1#$R/scratch/pads-core}; b=${3#$R/projects/programmable_transceiver_platform}
case $3 in $R/projects/*) b=/proj$b;; *) b=/work${3#$R/scratch/pads-core};; esac
$R/scratch/pads-core/dock.sh "python3 -c \"
import klayout.db as k
a=k.Layout();a.read('/work$a');b=k.Layout();b.read('$b')
ta=a.cell('$2');tb=b.cell('${4:-x}') or b.top_cell();tot=0
for li in a.layer_indexes():
  i=a.get_info(li);lj=b.find_layer(i.layer,i.datatype)
  ra=k.Region(ta.begin_shapes_rec(li));rb=k.Region(tb.begin_shapes_rec(lj)) if lj is not None else k.Region()
  tot+=(ra^rb).area()
for lj in b.layer_indexes():
  i=b.get_info(lj)
  if a.find_layer(i.layer,i.datatype) is None: tot+=k.Region(tb.begin_shapes_rec(lj)).area()
print('tops',[c.name for c in b.top_cells()],'XOR_AREA_UM2',tot*a.dbu*a.dbu)\"" 2>&1 | grep XOR_AREA
