for n in sc_tt_3.15 sc_tt_3.30 sc_tt_3.50 sc_ss_3.15 sc_ss_3.30 sc_ss_3.50 sc_ff_3.15 sc_ff_3.30 sc_ff_3.50; do ngspice -b $n.spice > $n.log 2>&1; done
