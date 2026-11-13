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
VEN en 0 pwl(0 0 5n 0 5.1n 3.63)
.tran 20p 400n
.control
run
meas tran t1 when v(clk)=1.815 rise=1 td=1e-07
meas tran t11 when v(clk)=1.815 rise=11 td=1e-07
meas tran clk_avg avg v(clk) from=1e-07 to=4e-07
meas tran x_avg avg v(x) from=1e-07 to=4e-07
meas tran x_pp pp v(x) from=1e-07 to=4e-07
meas tran ivdd_avg avg i(vdd) from=1e-07 to=4e-07
if ( t11 > t1 )
 let f_osc = 10/(t11-t1)
 print f_osc
end
.endc
.end
