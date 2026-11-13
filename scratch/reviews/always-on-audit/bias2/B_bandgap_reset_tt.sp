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
EH H 0 VDD 0 1
Xbandgap VDD VBG 0 BANDGAP_IBIAS1 L L L L L L L L H H H H H H H H L BANDGAP_IBIAS2 gf180mcu_ocd_ip__bandgap
R1 VBG 0 240k
R6 BANDGAP_IBIAS1 VDD 1e9
R7 BANDGAP_IBIAS2 VDD 1e9
Rr root_ref 0 1
.tran 0.2u 400u 0 0.2u
.control
run
meas tran ivdd_end find i(vdd) at=398u
meas tran ivdd_100u find i(vdd) at=100u
meas tran vbg_end find v(vbg) at=398u
meas tran root_end find v(root_ref) at=398u
.endc
.end
