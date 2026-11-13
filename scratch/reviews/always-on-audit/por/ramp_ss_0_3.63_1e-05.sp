* audit deck
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice ss
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice res_ss
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice mimcap_ss
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice diode_ss
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice bjt_ss
.include /foss/pdks/gf180mcuD/libs.ref/gf180mcu_as_sc_mcu7t3v3/spice/gf180mcu_as_sc_mcu7t3v3.spice
.temp 0
.option method=gear reltol=1e-4
.param ileak_audit=0.0
.include /work/por/por_leak.spice
Vdd vdd 0 pwl(0 0 1e-05 3.63)
Vena ena vdd 0
X1 vdd ena por_unbuf 0 porb por gf180mcu_ocd_ip__por
Cpb porb 0 1p
Cp por 0 1p
.save v(vdd) v(porb) v(por) i(vdd) v(x1.vcap)
.tran 1e-06 0.09000999999999999 0 4.5004999999999993e-05
.control
run
meas tran t_rel when v(porb)=1.815 rise=last
meas tran porb_end find v(porb) at=0.08991998999999999
meas tran porb_at_1v find v(porb) when v(vdd)=1.0 rise=1
meas tran vdd_at_rel find v(vdd) when v(porb)=0.5 rise=1
meas tran ivdd_end find i(vdd) at=0.08991998999999999
meas tran vcap_end find v(x1.vcap) at=0.08992
.endc
.end
