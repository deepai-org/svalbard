* audit deck
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice ff
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice res_ff
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice mimcap_ff
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice diode_ff
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice bjt_ff
.temp 0
.option gmin=1e-15 reltol=1e-4
.include /isl/pex/isw_conv/isw_conv.pex.spice
XI VDD VISL 0 EN ISO PG isw_conv_pex
VDD VDD 0 0
RL VISL 0 1e9
CEN EN 0 1f
.control
dc VDD 0 3.63 0.03
meas dc visl_max max v(visl)
meas dc en_max max v(en)
meas dc iso_end find v(iso) at=3.6
meas dc ivdd_end find i(vdd) at=3.6
meas dc visl_end find v(visl) at=3.6
.endc
.end
