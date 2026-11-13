* audit deck
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice ss
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice res_ss
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice mimcap_ss
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice diode_ss
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice bjt_ss
.temp 0
.option gmin=1e-15 reltol=1e-4
.include /isl/pex/isw_wired/isw_wired.pex.spice
XI VDD VISL 0 EN ISO PG isw_wired_pex
VDD VDD 0 pwl(0 0 0.001 3.63)
CI VISL 0 150p
RL VISL 0 1e9
.tran 1e-06 0.00155 0 5e-06
.control
run
meas tran visl_max max v(visl)
meas tran en_max max v(en)
meas tran iso_end find v(iso) at=0.0015344999999999998
meas tran visl_end find v(visl) at=0.0015344999999999998
.endc
.end
