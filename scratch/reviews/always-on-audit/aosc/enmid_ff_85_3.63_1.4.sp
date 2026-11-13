* audit deck
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice ff
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice res_ff
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice mimcap_ff
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice diode_ff
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice bjt_ff
.temp 85
.option gmin=1e-15 reltol=1e-4
.include /proj/analog/timing/generated/aosc.ext.spice
X1 en clk x vdd 0 pt_aosc
CL clk 0 20f
VDD vdd 0 3.63
VEN en 0 1.4
.tran 50p 1u
.control
run
meas tran ivdd_avg avg i(vdd) from=0.5u to=1u
meas tran clk_pp pp v(clk) from=0.5u to=1u
meas tran clk_avg avg v(clk) from=0.5u to=1u
.endc
.end
