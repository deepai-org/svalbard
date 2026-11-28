run(){ LIBPVT=$2 RC=$3 TC=$4 RATE=4 K=$5 DLY=max bash sta_b.sh $1 $6; }
run rf ss_032C_3v15 max ss_window 1.20 s315k120 & run wired ss_032C_3v15 max ss_window 1.20 s315k120; wait
run rf ss_032C_3v50 max ss_window 1.16 s350k116 & run wired ss_032C_3v50 max ss_window 1.16 s350k116; wait
run rf ff_n40C_3v60 min ff_window 1.0 ffn40 & run wired ff_n40C_3v60 min ff_window 1.0 ffn40; wait
echo DONE
