* audit skew deck
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice sf
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice res_typical
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice mimcap_typical
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice diode_typical
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice bjt_typical
.include /foss/pdks/gf180mcuD/libs.ref/gf180mcu_as_sc_mcu7t3v3/spice/gf180mcu_as_sc_mcu7t3v3.spice
.temp 0
.option method=gear reltol=1e-4
.param ileak_audit=0
.include /work/por/por_leak.spice
Vdd vdd 0 pwl(0 0 1e-3 3.15)
Vena ena vdd 0
X1 vdd ena por_unbuf 0 porb por gf180mcu_ocd_ip__por
Cpb porb 0 1p
Cp por 0 1p
.save v(vdd) v(porb) i(vdd)
.tran 1e-6 0.12 0 5e-5
.control
run
meas tran t_rel when v(porb)=1.575 rise=last
meas tran porb_end find v(porb) at=0.119
meas tran porb_at_1v find v(porb) when v(vdd)=1.0 rise=1
meas tran ivdd_end find i(vdd) at=0.119
.endc
.end
