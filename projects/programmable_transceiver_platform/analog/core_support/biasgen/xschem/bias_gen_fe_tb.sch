v {xschem version=3.4.6 file_version=3.3}
G {}
K {}
V {}
S {}
E {}
N 0 -620 110 -620 {
lab=ena}
N -70 -560 110 -560 {
lab=refsel}
N 410 -560 490 -560 {
lab=avss}
N 410 -600 490 -600 {
lab=avss}
N 410 -580 630 -580 {
lab=#net1}
N 410 -410 760 -410 {
lab=source0}
N 490 -600 490 -560 {lab=avss}
N 0 -410 110 -410 {lab=ena}
N 0 -380 110 -380 {lab=ena}
N 0 -410 0 -380 {lab=ena}
N 410 -380 800 -380 {lab=sink0}
N 90 -500 110 -500 {lab=ncasc}
N 90 -480 110 -480 {lab=nbias}
N 90 -460 110 -460 {lab=pcasc}
N 90 -440 110 -440 {lab=pbias}
N 0 -380 0 -310 {lab=ena}
N 560 -620 800 -620 {
lab=avdd}
N 760 -410 760 -310 {lab=source0}
N -140 -600 110 -600 {
lab=ref}
N -230 -580 110 -580 {
lab=vbg}
N 0 -620 0 -410 {lab=ena}
N -140 -600 -140 -310 {lab=ref}
N -230 -580 -230 -310 {lab=vbg}
N -390 -250 760 -250 {lab=GND}
N -310 -520 110 -520 {lab=fine}
N -310 -520 -310 -310 {lab=fine}
N -70 -560 -70 -310 {lab=refsel}
N -390 -540 -390 -310 {lab=coarse}
N -390 -540 110 -540 {lab=coarse}
N 800 -560 800 -380 {lab=sink0}
N 630 -580 630 -310 {lab=#net1}
N 560 -620 560 -310 {lab=avdd}
N 410 -620 560 -620 {
lab=avdd}
N 490 -560 490 -310 {lab=avss}
C {devices/vsource.sym} 560 -280 0 0 {name=Vavdd value=5.0 savecurrent=false}
C {devices/vsource.sym} 490 -280 0 0 {name=Vvss value=0 savecurrent=false}
C {devices/gnd.sym} 240 -250 0 0 {name=l1 lab=GND}
C {devices/vsource.sym} 760 -280 0 0 {name=Vsource0 value=1 savecurrent=false}
C {devices/vsource.sym} 800 -590 0 0 {name=Vsink0 value=1.5 savecurrent=false}
C {devices/lab_pin.sym} 760 -350 0 1 {name=p2 sig_type=std_logic lab=source0}
C {devices/lab_pin.sym} 800 -510 0 1 {name=p3 sig_type=std_logic lab=sink0}
C {devices/vsource.sym} -70 -280 0 0 {name=Vsel value=3.3 savecurrent=false}
C {devices/vsource.sym} -140 -280 0 0 {name=Vref value=DC 5.0 savecurrent=false}
C {devices/lab_wire.sym} -140 -600 0 1 {name=p5 sig_type=std_logic lab=ref}
C {devices/lab_wire.sym} 0 -620 0 1 {name=p6 sig_type=std_logic lab=ena}
C {devices/lab_wire.sym} 440 -600 0 1 {name=p8 sig_type=std_logic lab=avss}
C {devices/lab_wire.sym} 440 -620 0 1 {name=p9 sig_type=std_logic lab=avdd}
C {devices/code_shown.sym} -180 -200 0 0 {name=s1 only_toplevel=false value=".option savecurrents
.control
save all
dc Vref 5.0 1.5 -0.1
print I(vsink0) I(vsource0)
print I(v.x1.vmeas) I(v.x1.vmeas1) I(v.x1.vmeas2)
print V(nbias) V(pbias) V(ncasc) V(pcasc) V(x1.vfb)
print V(x1.x3.vcom) V(x1.x3.outn)
.endc"}
C {devices/code_shown.sym} -180 20 0 0 {name=s2 only_toplevel=false value=".lib $PDK_ROOT/gf180mcuD/libs.tech/ngspice/sm141064.spice typical
.lib $PDK_ROOT/gf180mcuD/libs.tech/ngspice/sm141064.spice diode_typical
.lib $PDK_ROOT/gf180mcuD/libs.tech/ngspice/sm141064.spice res_typical
.include $PDK_ROOT/gf180mcuD/libs.tech/ngspice/design.ngspice

.include $PDK_ROOT/gf180mcuD/libs.ref/gf180mcu_as_sc_mcu7t3v3/spice/gf180mcu_as_sc_mcu7t3v3.spice
"}
C {devices/vsource.sym} -230 -280 0 0 {name=Vbg value=3.3 savecurrent=false}
C {devices/lab_wire.sym} -230 -580 0 1 {name=p7 sig_type=std_logic lab=vbg}
C {devices/vsource.sym} 0 -280 0 0 {name=Vena1 value=3.3 savecurrent=false}
C {devices/lab_wire.sym} -70 -560 0 0 {name=p10 sig_type=std_logic lab=refsel}
C {devices/vsource.sym} 630 -280 0 0 {name=Vdvdd value=3.3 savecurrent=false}
C {bias_generator_fe.sym} 260 -400 0 0 {name=x1}
C {lab_pin.sym} 90 -440 0 0 {name=p11 sig_type=std_logic lab=pbias}
C {lab_pin.sym} 90 -460 0 0 {name=p12 sig_type=std_logic lab=pcasc}
C {lab_pin.sym} 90 -480 0 0 {name=p13 sig_type=std_logic lab=nbias}
C {lab_pin.sym} 90 -500 0 0 {name=p14 sig_type=std_logic lab=ncasc}
C {devices/vsource.sym} -310 -280 0 0 {name=Vfine value=0 savecurrent=false}
C {devices/lab_wire.sym} -310 -520 0 1 {name=p1 sig_type=std_logic lab=fine}
C {devices/vsource.sym} -390 -280 0 0 {name=Vcoarse value=0 savecurrent=false}
C {devices/lab_wire.sym} -390 -540 0 1 {name=p4 sig_type=std_logic lab=coarse}
