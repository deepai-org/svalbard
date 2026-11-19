#!/bin/bash
# usage: checks.sh <build under b/> [kl|rb|lu|rail ...]   independent layout checks, sequential (ONE job at a time)
cd /home/ubuntu/svalbard; export OMP_NUM_THREADS=1
T=/home/ubuntu/svalbard/scratch/pads-core/esdopt/tx; B=$T/b/$1; C=$T/checks/$1; mkdir -p $C/neg
P=projects/programmable_transceiver_platform; shift; PARTS=${@:-kl rb lu rail}
for p in $PARTS; do case $p in
kl) rm -rf $C/kldrc; python3 $P/verification/kl_block_drc.py --gds $B/pad_txpad.gds --top pad_txpad --name pad_txpad --out $C/kldrc --threads 1 > $C/kldrc.log 2>&1; echo "kldrc rc=$?" >> $C/progress;;
rb) rm -rf $C/rb
 python3 scratch/integration/signoff-gap/lvs/rb_lvs.py pos $B/pad_txpad.gds pad_txpad $B/schematic.spice pad_txpad --work $C/rb --cpus 1 > $C/rb_pos.log 2>&1; echo "rb_pos rc=$? verdict=$(python3 $T/rbverdict.py pos $C/rb_pos.log)" >> $C/progress
 scratch/pads-core/dock.sh "python3 /work/esdopt/tx/swap.py /work/esdopt/tx/b/$(basename $B)/pad_txpad.gds /work/esdopt/tx/checks/$(basename $B)/neg/swapped.gds pad_txpad MAIN_P MAIN_BIAS" > $C/swap.log 2>&1
 python3 scratch/integration/signoff-gap/lvs/rb_lvs.py neg $C/neg/swapped.gds pad_txpad $B/schematic.spice pad_txpad --work $C/rb --cpus 1 > $C/rb_neg.log 2>&1; echo "rb_neg rc=$? verdict=$(python3 $T/rbverdict.py neg $C/rb_neg.log $C/swap.log)" >> $C/progress
 rm -f $C/neg/swapped.gds;;
lu) bash scratch/pads-lu01/lu.sh $C/lu.json $B/pad_txpad.gds:pad_txpad > $C/lu.log 2>&1; echo "lu rc=$?" >> $C/progress;;
rail) scratch/pads-core/dock.sh "cd /work/esdopt/site && python3 railasm.py /work/esdopt/tx/b/$(basename $B)/pad_txpad.gds pad_txpad /work/esdopt/tx/checks/$(basename $B)/asm.gds 0 211 && python3 railconn.py /work/esdopt/tx/checks/$(basename $B)/asm.gds PAD=PAD_P VSS=VSS DVDD=DVDD_P --x 0,211 && python3 railconn.py /work/esdopt/tx/checks/$(basename $B)/asm.gds PAD=PAD_N VSS=VSS DVDD=DVDD_N --x 0,211" > $C/rail.log 2>&1; echo "rail rc=$?" >> $C/progress;;
esac; done
echo done >> $C/progress
