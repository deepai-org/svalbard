run(){ LIBPVT=$2 RC=$3 TC=$4 RATE=$5 K=$6 DLY=$7 bash sta.sh $1 $8; }
for c in rf wired; do
 run $c ss_032C_3v15 max ss_window 4 1.0 max s315k100 &
 run $c ss_032C_3v15 max ss_window 4 1.20 max s315k120; wait
 run $c ss_032C_3v15 max ss_window 4 1.14 max s315k114 &
 run $c ss_032C_3v50 max ss_window 4 1.0 max s350k100; wait
 run $c ss_032C_3v50 max ss_window 4 1.16 max s350k116 &
 run $c ff_n40C_3v60 min ff_window 4 1.0 min ffn40 ; wait
 run $c ff_022C_3v35 min ff_window 4 1.0 min ff22 &
 [ $c = rf ] && run $c ss_032C_3v50 max ss_window 1 1.0 max ka350r1; wait
done
echo DONE
