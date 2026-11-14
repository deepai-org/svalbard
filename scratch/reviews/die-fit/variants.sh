#!/bin/bash
# all die-fit packing runs, one after another, one thread
cd "$(dirname "$0")"
M=MACRO=1716:1262,1500:1300,2024:954; T=TRIES=6
./runset.sh b     SCEN=B $M $T
./runset.sh c     SCEN=C $M $T
./runset.sh b-h5  SCEN=B HALO=5 $M $T
./runset.sh c-h5  SCEN=C HALO=5 $M $T
L1=NOPAD=pad_bb_i,pad_bb_q,pad_wmon
./runset.sh c-l1  SCEN=C $L1 $M $T
./runset.sh c-l2  SCEN=C $L1 BANK=0 $M $T
./runset.sh c-l3  SCEN=C $L1 BANK=0 RING=36 $M $T
./runset.sh c-l4  SCEN=C $L1 BANK=0 RING=36 HALO=6 $M $T
./runset.sh c-l5  SCEN=C $L1 BANK=0 RING=36 HALO=6 DROP=char_rffet_open,char_rffet_short $M $T
./runset.sh b-l4  SCEN=B $L1 BANK=0 RING=36 HALO=6 $M $T
./runset.sh b-g500 SCEN=B GROW=500 $M $T
./runset.sh b-g700 SCEN=B GROW=700 $M $T
./runset.sh b-g900 SCEN=B GROW=900 $M $T
