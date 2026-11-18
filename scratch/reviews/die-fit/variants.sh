#!/bin/bash
# all die-fit packing runs on the current ledger, strictly one after another, one thread
# (2 macro shapes x 3 ordering strategies each; STRAT=2 = signal-flow / supply order only)
cd "$(dirname "$0")"
T=TRIES=3
L1=NOPAD=pad_bb_i,pad_bb_q,pad_wmon
D6=DROP=lo_mmd_qdum,lo_obs
./runset.sh s      SCEN=S TRIES=6
./runset.sh t      SCEN=T TRIES=6
./runset.sh lb     SCEN=LB TRIES=6
./runset.sh s-flow SCEN=S STRAT=2 $T
./runset.sh t-flow SCEN=T STRAT=2 $T
./runset.sh lb-flow SCEN=LB STRAT=2 $T
./runset.sh s-m28  SCEN=S MACRO_MM2=2.814 $T
./runset.sh s-m32  SCEN=S MACRO_MM2=3.200 $T
./runset.sh t-m36  SCEN=T MACRO_MM2=3.648 $T
./runset.sh t-m28  SCEN=T MACRO_MM2=2.814 $T
./runset.sh t-l1   SCEN=T $L1 $T
./runset.sh t-l2   SCEN=T $L1 BANK=0 $T
./runset.sh t-l3   SCEN=T $L1 BANK=0 RING=36 $T
./runset.sh t-l4   SCEN=T $L1 BANK=0 RING=36 $D6 $T
./runset.sh t-l4-m28 SCEN=T $L1 BANK=0 RING=36 $D6 MACRO_MM2=2.814 $T
./runset.sh t-l4-flow SCEN=T $L1 BANK=0 RING=36 $D6 STRAT=2 $T
./runset.sh s-l4   SCEN=S $L1 BANK=0 RING=36 $D6 $T
./runset.sh lb-l3  SCEN=LB BANK=0 RING=36 $T
./runset.sh lb-l3-flow SCEN=LB BANK=0 RING=36 STRAT=2 $T
./runset.sh lb-m32 SCEN=LB MACRO_MM2=3.200 $T
./runset.sh lb-m36 SCEN=LB MACRO_MM2=3.648 $T
echo ALLDONE >> run/runset.status
