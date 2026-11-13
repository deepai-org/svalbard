* audit deck
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice res_typical
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice mimcap_typical
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice diode_typical
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice bjt_typical
.include /foss/pdks/gf180mcuD/libs.ref/gf180mcu_as_sc_mcu7t3v3/spice/gf180mcu_as_sc_mcu7t3v3.spice
.temp 27
.option method=gear reltol=1e-3 rshunt=1e12 cshunt=1e-17
.param ileak_audit=0.0
.include /clean/por/layout_pex.spice
Vdd vdd 0 pwl(0 0 0.001 3.3)
Vena ena vdd 0
X1 vdd ena por_unbuf 0 porb por gf180mcu_ocd_ip__por
Cpb porb 0 1p
Cp por 0 1p
.save v(vdd) v(porb) v(por) i(vdd)
.tran 1e-06 0.091 0 4.55e-05
.control
run
meas tran t_rel when v(porb)=1.65 rise=last
meas tran porb_end find v(porb) at=0.090909
meas tran porb_at_1v find v(porb) when v(vdd)=1.0 rise=1
meas tran vdd_at_rel find v(vdd) when v(porb)=0.5 rise=1
meas tran ivdd_end find i(vdd) at=0.090909
.endc
.end
