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
VDD vdd 0 3.3
VEN en 0 0
.control
dc VEN 0 3.3 0.05
meas dc ivdd_max min i(vdd)
meas dc ven_at_max when i(vdd)=ivdd_max
meas dc i_at_1v find i(vdd) at=1.0
meas dc i_at_1v5 find i(vdd) at=1.5
.endc
.end
