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
VDD vdd 0 pwl(0 0 1e-05 3.63)
REN vdd en 100
.tran 50p 1.1500000000000002e-05
.control
run
meas tran t1 when v(clk)=1.815 rise=1 td=1.1000000000000001e-05
meas tran t11 when v(clk)=1.815 rise=11 td=1.1000000000000001e-05
meas tran clk_avg avg v(clk) from=1.1000000000000001e-05 to=1.1500000000000002e-05
meas tran x_avg avg v(x) from=1.1000000000000001e-05 to=1.1500000000000002e-05
meas tran x_pp pp v(x) from=1.1000000000000001e-05 to=1.1500000000000002e-05
meas tran ivdd_avg avg i(vdd) from=1.1000000000000001e-05 to=1.1500000000000002e-05
if ( t11 > t1 )
 let f_osc = 10/(t11-t1)
 print f_osc
end
.endc
.end
