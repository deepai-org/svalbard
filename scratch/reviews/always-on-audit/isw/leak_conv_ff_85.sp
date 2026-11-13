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
VDD VDD 0 3.63
VEN EN 0 0
VISL VISL 0 0
.control
op
let ileak = i(visl)
print ileak
let ivdd = -i(vdd)
print ivdd
let v_iso = v(iso)
print v_iso
let v_pg = v(pg)
print v_pg
.endc
.end
