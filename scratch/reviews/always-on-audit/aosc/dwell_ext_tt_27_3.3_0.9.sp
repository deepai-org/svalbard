* audit deck
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice res_typical
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice mimcap_typical
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice diode_typical
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice bjt_typical
.temp 27
.option gmin=1e-15 reltol=1e-4
.include /proj/analog/timing/generated/aosc.ext.spice
X1 en clk x vdd 0 pt_aosc
CL clk 0 20f
VDD vdd 0 pwl(0 0 1u 0.9 2.1000000000000002e-05 0.9 2.6000000000000002e-05 3.3)
REN vdd en 100
.tran 50p 2.75e-05
.control
run
meas tran t1 when v(clk)=1.65 rise=1 td=2.65e-05
meas tran t11 when v(clk)=1.65 rise=11 td=2.65e-05
meas tran clk_avg avg v(clk) from=2.65e-05 to=2.75e-05
meas tran x_avg avg v(x) from=2.65e-05 to=2.75e-05
meas tran x_pp pp v(x) from=2.65e-05 to=2.75e-05
meas tran x_hold_avg avg v(x) from=1.6000000000000003e-05 to=2.1000000000000002e-05
meas tran x_hold_pp pp v(x) from=1.6000000000000003e-05 to=2.1000000000000002e-05
meas tran clk_hold_pp pp v(clk) from=1.6000000000000003e-05 to=2.1000000000000002e-05
let f_osc = 10/(t11-t1)
print f_osc
.endc
.end
