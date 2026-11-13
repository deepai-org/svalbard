* audit skew deck
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice fs
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice res_typical
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice mimcap_typical
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice diode_typical
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice bjt_typical
.include /foss/pdks/gf180mcuD/libs.ref/gf180mcu_as_sc_mcu7t3v3/spice/gf180mcu_as_sc_mcu7t3v3.spice
.temp 0
.option gmin=1e-15 reltol=1e-4
.include /proj/analog/timing/generated/aosc.ext.spice
X1 en clk x vdd 0 pt_aosc
CL clk 0 20f
VDD vdd 0 3.15
VEN en 0 pwl(0 0 5n 0 5.1n 3.15)
.tran 20p 400n
.control
run
meas tran t1 when v(clk)=1.575 rise=1 td=100n
meas tran t11 when v(clk)=1.575 rise=11 td=100n
let f_osc = 10/(t11-t1)
print f_osc
.endc
.end
