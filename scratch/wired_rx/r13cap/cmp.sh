#!/bin/bash
cd /home/ubuntu/svalbard/scratch/wired_rx; export OMP_NUM_THREADS=1
(cd r11/chain && ../../slot.sh python3 rb11.py ss315 2.5 rcs=0 cap=/home/ubuntu/svalbard/scratch/wired_rx/r13cap/gen/wrx_cap.ext.spice > r8_b25.log 2>&1) &
(cd r12/r6m4 && ../../slot.sh python3 g.py pess_q625_ss >> g.log 2>&1; ../../slot.sh python3 g.py f500_ss >> g.log 2>&1) &
(cd r13cap && ../slot.sh python3 g8.py f500_ss >> g8.log 2>&1) &
wait; date > r13cap/cmp.done
