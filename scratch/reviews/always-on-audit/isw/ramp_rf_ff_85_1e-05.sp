* audit deck
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice ff
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice res_ff
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice mimcap_ff
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice diode_ff
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice bjt_ff
.temp 85
.option gmin=1e-15 reltol=1e-4
.include /isl/pex/isw_rf/isw_rf.pex.spice
XI VDD VISL 0 EN ISO PG isw_rf_pex
VDD VDD 0 pwl(0 0 1e-05 3.63)
CI VISL 0 150p
RL VISL 0 1e9
.tran 1e-08 6.500000000000001e-05 0 5.0000000000000004e-08
.control
run
meas tran visl_max max v(visl)
meas tran en_max max v(en)
meas tran iso_end find v(iso) at=6.435e-05
meas tran visl_end find v(visl) at=6.435e-05
.endc
.end
