* audit deck
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice ff
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice res_ff
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice mimcap_ff
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice diode_ff
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice bjt_ff
.temp 85
.option gmin=1e-15 reltol=1e-4
.include /isl/pex/isw_conv/isw_conv.pex.spice
XI VDD VISL 0 EN ISO PG isw_conv_pex
VDD VDD 0 pwl(0 0 1e-3 3.63)
REN VDD EN 100
CI VISL 0 150p
RL VISL 0 1e9
.tran 1u 1.6e-3 0 5u
.control
run
meas tran visl_max max v(visl)
meas tran iso_end find v(iso) at=1.58e-3
meas tran visl_end find v(visl) at=1.58e-3
.endc
.end
