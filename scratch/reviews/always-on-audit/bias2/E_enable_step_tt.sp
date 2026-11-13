* audit deck
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice res_typical
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice mimcap_typical
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice diode_typical
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice bjt_typical
.temp 27
.option gmin=1e-14 reltol=1e-3 method=gear
.include /work/bias2/models.spice
VDD VDD 0 pwl(0 0 10u 3.3)
VL L 0 0
VEN EN 0 pwl(0 0 100u 0 100.1u 3.3)
Rld VBG 0 240k

EH H 0 VDD 0 1
Xbiasgen EN VDD VDD VBG L 0 IDAC1 L H L H L ROOT_REF L L L L L L L L L L VGEN_SOURCE L L BANDGAP_IBIAS1 H H H H H L L L L L L VGEN_SINK2 VGEN_SINK1 BANDGAP_IBIAS2 VDD gf180mcu_ocd_ip__biasgen
XD ROOT_REF ROOT_REF 0 0 nfet_03v3 w=8u l=4u
R1 VBG 0 240k
R2 IDAC1 0 1e9
R3 VGEN_SOURCE 0 1e9
R4 VGEN_SINK1 VDD 1e9
R5 VGEN_SINK2 VDD 1e9
Xbandgap VDD VBG 0 BANDGAP_IBIAS1 L L L L L L L L H H H H H H H H EN BANDGAP_IBIAS2 gf180mcu_ocd_ip__bandgap
.tran 0.2u 400u 0 0.2u
.control
run
meas tran vbg_pk max v(vbg) from=100u to=398u
meas tran t_up when v(vbg)=1.3 rise=1 td=100u
meas tran t_dn when v(vbg)=1.3 fall=1 td=100u
meas tran t_set when v(vbg)=1.25 fall=last
set wr_singlescale
set wr_vecnames
wrdata /work/bias2/en_step_wave.txt v(vbg) v(root_ref) i(vdd)
meas tran ivdd_end find i(vdd) at=398u
meas tran ivdd_100u find i(vdd) at=100u
meas tran vbg_end find v(vbg) at=398u
meas tran root_end find v(root_ref) at=398u
.endc
.end
