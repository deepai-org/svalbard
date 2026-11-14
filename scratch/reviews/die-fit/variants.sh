#!/bin/bash
# all die-fit packing runs on ledger v2, one after another, one thread (2 macro shapes x 3 ordering strategies each)
cd "$(dirname "$0")"
M=MACRO=1716:1262,2024:954; T=TRIES=3
L1=NOPAD=pad_bb_i,pad_bb_q,pad_wmon
./runset.sh b     SCEN=B $M TRIES=6
./runset.sh c     SCEN=C $M TRIES=6
./runset.sh cr    SCEN=CR $M $T
./runset.sh b-flow SCEN=B STRAT=2 $M $T
./runset.sh c-flow SCEN=C STRAT=2 $M $T
./runset.sh b-h5  SCEN=B HALO=5 $M $T
./runset.sh c-h5  SCEN=C HALO=5 $M $T
./runset.sh c-l1  SCEN=C $L1 $M $T
./runset.sh c-l2  SCEN=C $L1 BANK=0 $M $T
./runset.sh c-l3  SCEN=C $L1 BANK=0 RING=36 $M $T
./runset.sh c-l4  SCEN=C $L1 BANK=0 RING=36 HALO=6 $M $T
./runset.sh c-l5  SCEN=C $L1 BANK=0 RING=36 HALO=6 DROP=char_rffet_open,char_rffet_short $M $T
./runset.sh c-l5-flow SCEN=C $L1 BANK=0 RING=36 HALO=6 DROP=char_rffet_open,char_rffet_short STRAT=2 $M $T
./runset.sh cr-l5 SCEN=CR $L1 BANK=0 RING=36 HALO=6 DROP=char_rffet_open,char_rffet_short $M $T
./runset.sh b-l5  SCEN=B $L1 BANK=0 RING=36 HALO=6 DROP=char_rffet_open,char_rffet_short $M $T
./runset.sh b-g500 SCEN=B GROW=500 $M $T
./runset.sh b-g700 SCEN=B GROW=700 $M $T
./runset.sh b-g900 SCEN=B GROW=900 $M $T
./runset.sh b-g1100 SCEN=B GROW=1100 $M $T

D6=DROP=char_rffet_open,char_rffet_short,lo_mmd_qdum,lo_obs
./runset.sh c-l6  SCEN=C $L1 BANK=0 RING=36 $D6 $M $T
./runset.sh cr-l6 SCEN=CR $L1 BANK=0 RING=36 $D6 $M $T
./runset.sh b-l6  SCEN=B $L1 BANK=0 RING=36 $D6 $M $T
