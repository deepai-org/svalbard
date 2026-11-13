* audit deck
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice res_typical
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice mimcap_typical
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice diode_typical
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice bjt_typical
.temp 27
.option gmin=1e-15 reltol=1e-4
.include /proj/analog/timing/aosc.spice
X1 en clk x vdd 0 pt_aosc
CL clk 0 20f
VDD vdd 0 3.3
VEN en 0 0
.tran 20p 400n
.control
run
meas tran t1 when v(clk)=1.65 rise=1 td=1e-07
meas tran t11 when v(clk)=1.65 rise=11 td=1e-07
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
