#!/bin/bash
# usage: checks.sh <build name>   independent layout checks on build/<name>/pad/combined.gds (top tx_with_primary), sequential -> checks/<name>/
# (pattern: ../hs/sec/checks_s.sh). ONE job at a time.
cd /home/ubuntu/svalbard; export OMP_NUM_THREADS=1
U=/home/ubuntu/svalbard/scratch/pads-core/esdopt/ref; B=$U/build/$1/pad; C=$U/checks/$1; T=tx_with_primary
P=projects/programmable_transceiver_platform
rm -rf $C; mkdir -p $C/neg
# read-back LVS on the GDS from disk, flattened (the site-diode primitives are subcells; netgen's hierarchical pin match fails on them)
scratch/pads-core/dock.sh "python3 -c \"
import klayout.db as k
l=k.Layout(); l.read('/work/esdopt/ref/build/$1/pad/combined.gds'); t=l.cell('$T'); t.flatten(True)
o=k.SaveLayoutOptions(); o.add_cell(t.cell_index()); l.write('/work/esdopt/ref/checks/$1/flat.gds', o)\"" > $C/flat.log 2>&1
python3 - $B/physical.spice $C/lvs-reference.spice <<'PY'
import re, sys
t = open(sys.argv[1]).read(); b = re.search(r'(?ms)^\.subckt combined_flat .*?^\.ends[^\n]*\n?', t).group(0); open(sys.argv[2], 'w').write(b)
lines = b.splitlines(); i = next((k for k, l in enumerate(lines) if re.match(r'D\d+ PAD_P DVDD diode_pd2nw_06v0', l)), None)
if i is not None: del lines[i]; open(sys.argv[2].replace('.spice', '-neg.spice'), 'w').write('\n'.join(lines) + '\n')
PY
python3 scratch/integration/signoff-gap/lvs/rb_lvs.py pos $C/flat.gds $T $C/lvs-reference.spice combined_flat --work $C/rb --cpus 1 > $C/rb_pos.log 2>&1; echo "rb_pos rc=$?" > $C/progress
python3 scratch/integration/signoff-gap/lvs/rb_lvs.py sch $C/flat.gds $T $B/reference.spice expected --work $C/rb --cpus 1 > $C/rb_sch.log 2>&1; echo "rb_sch rc=$?" >> $C/progress
scratch/pads-core/dock.sh "python3 -c \"
import klayout.db as k
l=k.Layout(); l.read('/work/esdopt/ref/checks/$1/flat.gds'); t=l.cell('$T'); n=0
for li in l.layer_indexes():
  for s in t.shapes(li).each():
    if s.is_text() and s.text_string in ('VCM','VSS'):
      tx=s.text; tx.string='VSS' if tx.string=='VCM' else 'VCM'; s.text=tx; n+=1
print('swapped',n); l.write('/work/esdopt/ref/checks/$1/neg/swapped.gds')\"" > $C/swap.log 2>&1
python3 scratch/integration/signoff-gap/lvs/rb_lvs.py neg $C/neg/swapped.gds $T $C/lvs-reference.spice combined_flat --work $C/rb --cpus 1 > $C/rb_neg.log 2>&1; echo "rb_neg (VCM/VSS label swap; PAD_P/N swap is symmetric and matches) rc=$? (must fail)" >> $C/progress
rm -f $C/neg/swapped.gds
[ -f $C/lvs-reference-neg.spice ] && { python3 scratch/integration/signoff-gap/lvs/rb_lvs.py neg2 $C/flat.gds $T $C/lvs-reference-neg.spice combined_flat --work $C/rb --cpus 1 > $C/rb_neg2.log 2>&1; echo "rb_neg2 (one site diode missing in the reference) rc=$? (must fail)" >> $C/progress; }
scratch/pads-core/dock.sh "python3 -c \"
import klayout.db as k
l = k.Layout(); l.read('/work/esdopt/ref/build/$1/pad/combined.gds'); t = l.cell('$T')
B = lambda ly, x1, y1, x2, y2: t.shapes(l.layer(ly, 0)).insert(k.DBox(x1, y1, x2, y2))
B(34, 400, 1000, 400.1, 1010)
B(22, 400, 1100, 402, 1104); B(30, 400.8, 1099.4, 401.2, 1104.6); B(32, 399.8, 1099.8, 402.2, 1104.2)
l.write('/work/esdopt/ref/checks/$1/neg/ctrl.gds')\"" > $C/ctrl.log 2>&1
python3 $P/verification/kl_block_drc.py --gds $C/neg/ctrl.gds --top $T --name ctrl --out $C/kldrc_ctrl --threads 1 > $C/kldrc_ctrl.log 2>&1; echo "kldrc CONTROL (sliver) rc=$? (must report violations)" >> $C/progress
bash scratch/pads-lu01/lu.sh $C/lu_ctrl.json $C/neg/ctrl.gds:$T > $C/lu_ctrl.log 2>&1; echo "lu CONTROL (isolated nmos) rc=$? (must report uncovered area)" >> $C/progress
rm -f $C/neg/ctrl.gds
python3 $P/analog/pads/rail_site_check.py --gds $B/combined.gds --top $T --name ref_$1 --out $C/railsite --threads 1 > $C/railsite.log 2>&1; echo "rail_site_check rc=$?" >> $C/progress
python3 $P/analog/pads/rail_site_check.py --selftest --out $C/railsite_selftest > $C/railsite_selftest.log 2>&1; echo "rail_site_check selftest rc=$?" >> $C/progress
python3 $P/verification/kl_block_drc.py --gds $B/combined.gds --top $T --name $T --out $C/kldrc --threads 1 > $C/kldrc.log 2>&1; echo "kldrc rc=$?" >> $C/progress
bash scratch/pads-lu01/lu.sh $C/lu.json $B/combined.gds:$T > $C/lu.log 2>&1; echo "lu rc=$?" >> $C/progress
scratch/pads-core/dock.sh "cd /work/esdopt/site && python3 railasm.py /work/esdopt/ref/build/$1/pad/combined.gds $T /work/esdopt/ref/checks/$1/asm.gds 0 211 && python3 railconn.py /work/esdopt/ref/checks/$1/asm.gds PAD_P=PAD_P PAD_N=PAD_N VSS=VSS DVDD=DVDD VCM=VCM --x 0,211" > $C/railconn.txt 2>&1; echo "railconn: $(tail -1 $C/railconn.txt)" >> $C/progress
scratch/pads-core/esdopt/site/railcap.sh $C > $C/railcap.txt 2>&1; echo "railcap done" >> $C/progress
python3 $P/verification/kl_block_drc.py --gds $C/asm.gds --top asm --name asm --out $C/kldrc_rail --threads 1 > $C/kldrc_rail.log 2>&1; echo "kldrc pad-on-rail rc=$?" >> $C/progress
rm -f $C/asm.gds
echo "floating: $(grep -c 'FLOATING' $B/physical.spice) line(s)" >> $C/progress
rm -f $C/flat.gds
echo done >> $C/progress
