v {xschem version=3.4.6 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
T {step down 12x} 470 280 0 0 0.4 0.4 {}
T {step down 12x} 360 -250 0 0 0.4 0.4 {}
T {step down 9x} 650 -250 0 0 0.4 0.4 {}
T {512nA} 270 -220 0 0 0.3 0.3 {}
T {43nA} 410 -220 0 0 0.3 0.3 {}
T {3.6nA} 560 -220 0 0 0.3 0.3 {}
T {400pA} 710 -220 0 0 0.3 0.3 {}
T {POR with 40ms reset delay (self-biased)} -130 -340 0 0 0.5 0.5 {}
T {dummy devices} 1310 90 0 0 0.3 0.3 {}
N -180 -180 0 -180 {lab=vdd3v3}
N 0 50 0 260 {lab=vss}
N 290 -180 900 -180 {lab=vdd3v3}
N 290 10 290 40 {lab=#net1}
N 290 100 290 130 {lab=vfb}
N 240 160 270 160 {lab=vss}
N 240 160 240 260 {lab=vss}
N 290 70 360 70 {lab=vdd3v3}
N 290 -20 360 -20 {lab=vdd3v3}
N 430 -70 490 -70 {lab=vdd3v3}
N 220 30 390 30 {lab=vfb}
N 220 30 220 70 {lab=vfb}
N 230 -70 230 -20 {lab=vpb}
N 230 -70 390 -70 {lab=vpb}
N 430 -40 430 -0 {lab=p1}
N 430 60 430 90 {lab=nb1}
N 430 150 430 180 {lab=#net2}
N 430 240 430 260 {lab=vss}
N 380 120 430 120 {lab=vss}
N 380 120 380 260 {lab=vss}
N 380 210 430 210 {lab=vss}
N 430 70 470 70 {lab=nb1}
N 470 70 470 120 {lab=nb1}
N 430 160 470 160 {lab=#net2}
N 470 160 470 210 {lab=#net2}
N 470 210 540 210 {lab=#net2}
N 470 120 540 120 {lab=nb1}
N 580 150 580 180 {lab=n1}
N 580 240 580 260 {lab=vss}
N 580 120 650 120 {lab=vss}
N 650 120 650 260 {lab=vss}
N 580 210 650 210 {lab=vss}
N 430 30 490 30 {lab=vdd3v3}
N 490 -70 490 30 {lab=vdd3v3}
N 580 -50 580 -10 {lab=#net3}
N 580 50 580 90 {lab=pb1}
N 580 -30 620 -30 {lab=#net3}
N 620 -80 620 -30 {lab=#net3}
N 580 70 620 70 {lab=pb1}
N 620 20 620 70 {lab=pb1}
N 620 20 690 20 {lab=pb1}
N 620 -80 690 -80 {lab=#net3}
N 730 -50 730 -10 {lab=p2}
N 730 -80 790 -80 {lab=vdd3v3}
N 730 20 790 20 {lab=vdd3v3}
N 790 -80 790 20 {lab=vdd3v3}
N 220 70 250 70 {lab=vfb}
N 520 20 580 20 {lab=vdd3v3}
N 520 -80 580 -80 {lab=vdd3v3}
N 730 70 830 70 {lab=vcap}
N 900 140 900 260 {lab=vss}
N 1020 70 1070 70 {lab=por_unbuf}
N -210 260 0 260 {lab=vss}
N 290 190 290 260 {lab=vss}
N 790 -180 790 -80 {lab=vdd3v3}
N 900 -180 900 -0 {lab=vdd3v3}
N 520 -180 520 20 {lab=vdd3v3}
N 490 -180 490 -70 {lab=vdd3v3}
N 360 -180 360 70 {lab=vdd3v3}
N 0 -180 0 -90 {lab=vdd3v3}
N 730 -120 730 -110 {lab=#net4}
N 580 -120 580 -110 {lab=#net5}
N 430 -120 430 -100 {lab=#net6}
N 290 -120 290 -50 {lab=#net7}
N 220 70 220 110 {lab=vfb}
N 1180 -50 1340 -50 {lab=por}
N 1300 20 1340 20 {lab=porb}
N 1190 20 1220 20 {lab=#net8}
N 1040 20 1110 20 {lab=por_unbuf}
N 1040 20 1040 70 {lab=por_unbuf}
N 1040 -50 1040 20 {lab=por_unbuf}
N 1040 -50 1100 -50 {lab=por_unbuf}
N -120 -100 -120 30 {lab=vref}
N -120 -180 -120 -160 {lab=vdd3v3}
N -160 -130 -140 -130 {lab=vss}
N -210 -10 -70 -10 {lab=ena}
N -120 180 -120 190 {lab=#net9}
N -120 250 -120 260 {lab=vss}
N -200 50 -200 260 {lab=vss}
N -200 150 -120 150 {lab=vss}
N -200 220 -120 220 {lab=vss}
N -120 90 -120 120 {lab=#net10}
N -120 120 -80 120 {lab=#net10}
N -80 120 -80 150 {lab=#net10}
N -120 190 -80 190 {lab=#net9}
N -80 190 -80 220 {lab=#net9}
N -70 30 -70 110 {lab=vfb}
N -120 -70 -70 -70 {lab=vref}
N 30 50 30 190 {lab=#net9}
N -80 190 30 190 {lab=#net9}
N 100 -20 250 -20 {lab=vpb}
N 0 -180 290 -180 {lab=vdd3v3}
N 0 260 900 260 {lab=vss}
N -70 110 290 110 {lab=vfb}
N 730 50 730 150 {lab=vcap}
N 730 210 730 260 {lab=vss}
N 100 40 100 70 {lab=vref}
N 1080 180 1140 180 {lab=vdd3v3}
N 1140 150 1140 180 {lab=vdd3v3}
N 1080 150 1140 150 {lab=vdd3v3}
N 1080 210 1140 210 {lab=vdd3v3}
N 1140 180 1140 210 {lab=vdd3v3}
N 1030 210 1080 210 {lab=vdd3v3}
N 1030 180 1030 210 {lab=vdd3v3}
N 1030 180 1040 180 {lab=vdd3v3}
N 1270 130 1270 150 {lab=p1}
N 1270 180 1320 180 {lab=vdd3v3}
N 1320 180 1320 210 {lab=vdd3v3}
N 1270 210 1320 210 {lab=vdd3v3}
N 1230 210 1270 210 {lab=vdd3v3}
N 1230 180 1230 210 {lab=vdd3v3}
N 1140 210 1230 210 {lab=vdd3v3}
N 1430 130 1430 150 {lab=p1}
N 1430 180 1480 180 {lab=vdd3v3}
N 1390 180 1390 210 {lab=vdd3v3}
N 1430 210 1430 230 {lab=vfb}
N 1320 210 1390 210 {lab=vdd3v3}
N 1620 130 1620 150 {lab=vfb}
N 1620 180 1670 180 {lab=vdd3v3}
N 1580 180 1580 210 {lab=vdd3v3}
N 1580 210 1670 210 {lab=vdd3v3}
N 1670 180 1670 210 {lab=vdd3v3}
N 1030 300 1040 300 {lab=vss}
N 1030 300 1030 330 {lab=vss}
N 1030 330 1140 330 {lab=vss}
N 1140 300 1140 330 {lab=vss}
N 1080 300 1140 300 {lab=vss}
N 1080 270 1140 270 {lab=vss}
N 1140 270 1140 300 {lab=vss}
N 1270 250 1270 270 {lab=n1}
N 1140 330 1270 330 {lab=vss}
N 1270 330 1320 330 {lab=vss}
N 1320 300 1320 330 {lab=vss}
N 1270 300 1320 300 {lab=vss}
N 1230 300 1230 330 {lab=vss}
N 1480 250 1480 270 {lab=n1}
N 1480 300 1530 300 {lab=vss}
N 1440 300 1440 330 {lab=vss}
N 1320 330 1440 330 {lab=vss}
N 1480 330 1480 350 {lab=nb1}
N 1600 300 1600 330 {lab=vss}
N 1600 330 1690 330 {lab=vss}
N 1690 300 1690 330 {lab=vss}
N 1640 300 1690 300 {lab=vss}
N 1640 250 1640 270 {lab=nb1}
N 1260 380 1260 400 {lab=p2}
N 1260 430 1310 430 {lab=vdd3v3}
N 1310 430 1310 460 {lab=vdd3v3}
N 1260 460 1310 460 {lab=vdd3v3}
N 1220 460 1260 460 {lab=vdd3v3}
N 1220 430 1220 460 {lab=vdd3v3}
N 1420 380 1420 400 {lab=p2}
N 1420 430 1470 430 {lab=vdd3v3}
N 1380 430 1380 460 {lab=vdd3v3}
N 1420 460 1420 480 {lab=pb1}
N 1310 460 1380 460 {lab=vdd3v3}
N 1610 380 1610 400 {lab=pb1}
N 1610 430 1660 430 {lab=vdd3v3}
N 1570 430 1570 460 {lab=vdd3v3}
N 1570 460 1660 460 {lab=vdd3v3}
N 1660 430 1660 460 {lab=vdd3v3}
C {por_amp.sym} 10 -20 0 0 {name=x1}
C {por_3v3_schmitt_inv.sym} 920 70 0 0 {name=x2}
C {ipin.sym} -210 -10 0 0 {name=p1 lab=ena}
C {symbols/nfet_03v3.sym} 450 120 0 1 {name=M1
L=0.28u
W=6u
nf=12
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {symbols/pfet_03v3.sym} 270 -20 0 0 {name=M2
L=0.28u
W=6.0u
nf=12
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {iopin.sym} -180 -180 0 1 {name=p3 lab=vdd3v3}
C {iopin.sym} -210 260 0 1 {name=p4 lab=vss}
C {symbols/ppolyf_u_1k.sym} 290 160 0 0 {name=R1
W=1e-6
L=2500e-6
model=ppolyf_u_1k
spiceprefix=X
m=1}
C {symbols/pfet_03v3.sym} 270 70 0 0 {name=M3
L=0.28u
W=6u
nf=12
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {symbols/pfet_03v3.sym} 410 -70 0 0 {name=M4
L=0.28u
W=0.5u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {symbols/pfet_03v3.sym} 410 30 0 0 {name=M5
L=0.28u
W=0.5u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {symbols/nfet_03v3.sym} 450 210 0 1 {name=M6
L=0.28u
W=6u
nf=12
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {symbols/nfet_03v3.sym} 560 120 0 0 {name=M7
L=0.28u
W=0.5u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {symbols/nfet_03v3.sym} 560 210 0 0 {name=M8
L=0.28u
W=0.5u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {symbols/pfet_03v3.sym} 600 20 0 1 {name=M9
L=0.28u
W=4u
nf=8
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {symbols/pfet_03v3.sym} 600 -80 0 1 {name=M10
L=0.28u
W=4u
nf=8
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {symbols/pfet_03v3.sym} 710 -80 0 0 {name=M11
L=0.28u
W=0.5u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {symbols/pfet_03v3.sym} 710 20 0 0 {name=M12
L=0.28u
W=0.5u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {symbols/cap_mim_2f0fF.sym} 730 180 0 0 {name=C1
W=10e-6
L=10e-6
model=cap_mim_2f0_m4m5_noshield
spiceprefix=X
m=36}
C {opin.sym} 1070 70 0 0 {name=p5 lab=por_unbuf}
C {symbols/diode_nd2ps_03v3.sym} -200 20 2 0 {name=D1
model=diode_nd2ps_03v3
r_w=0.45u
r_l=0.45u
m=1}
C {lab_wire.sym} 810 70 0 0 {name=p6 sig_type=std_logic lab=vcap}
C {ammeter.sym} 290 -150 0 0 {name=Vmeas savecurrent=true spice_ignore=0}
C {ammeter.sym} 430 -150 0 0 {name=Vmeas1 savecurrent=true spice_ignore=0}
C {ammeter.sym} 580 -150 0 0 {name=Vmeas2 savecurrent=true spice_ignore=0}
C {ammeter.sym} 730 -150 0 0 {name=Vmeas3 savecurrent=true spice_ignore=0}
C {lab_wire.sym} 160 110 0 0 {name=p7 sig_type=std_logic lab=vfb}
C {lab_wire.sym} 140 -20 0 0 {name=p8 sig_type=std_logic lab=vpb}
C {fillcap_4.sym} 1160 -130 0 0 {name=x3[1:0] VDD=vdd3v3 VNW=vdd3v3 VPW=vss VSS=vss prefix=gf180mcu_as_sc_mcu7t3v3__ }
C {tap_2.sym} 1160 -180 0 0 {name=x4[1:0] VSS=vss VDD=vdd3v3 prefix=gf180mcu_as_sc_mcu7t3v3__ }
C {buff_12.sym} 1140 -50 0 0 {name=x5 VDD=vdd3v3 VNW=vdd3v3 VPW=vss VSS=vss prefix=gf180mcu_as_sc_mcu7t3v3__ }
C {inv_4.sym} 1150 20 0 0 {name=x6 VDD=vdd3v3 VNW=vdd3v3 VPW=vss VSS=vss prefix=gf180mcu_as_sc_mcu7t3v3__ }
C {buff_12.sym} 1260 20 0 0 {name=x3 VDD=vdd3v3 VNW=vdd3v3 VPW=vss VSS=vss prefix=gf180mcu_as_sc_mcu7t3v3__ }
C {opin.sym} 1340 20 0 0 {name=p9 lab=porb}
C {opin.sym} 1340 -50 0 0 {name=p10 lab=por}
C {symbols/ppolyf_u_1k.sym} -120 -130 0 0 {name=R2
W=1e-6
L=2500e-6
model=ppolyf_u_1k
spiceprefix=X
m=1}
C {lab_pin.sym} -160 -130 0 0 {name=p2 sig_type=std_logic lab=vss}
C {lab_pin.sym} -120 -70 0 0 {name=p11 sig_type=std_logic lab=vref}
C {ammeter.sym} -120 60 0 1 {name=Vmeas4 savecurrent=true spice_ignore=0}
C {symbols/nfet_03v3.sym} -100 220 0 1 {name=M13
L=0.28u
W=8.0u
nf=8
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {symbols/nfet_03v3.sym} -100 150 0 1 {name=M14
L=0.28u
W=8.0u
nf=8
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {lab_pin.sym} 100 70 0 0 {name=p12 sig_type=std_logic lab=vref}
C {symbols/pfet_03v3.sym} 1060 180 0 0 {name=M15
L=0.28u
W=0.5u
nf=1
m=2
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {lab_pin.sym} 1030 210 0 0 {name=p13 sig_type=std_logic lab=vdd3v3}
C {lab_pin.sym} 430 -20 0 1 {name=p14 sig_type=std_logic lab=p1}
C {symbols/pfet_03v3.sym} 1250 180 0 0 {name=M16
L=0.28u
W=0.5u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {lab_pin.sym} 1270 130 0 0 {name=p15 sig_type=std_logic lab=p1}
C {symbols/pfet_03v3.sym} 1410 180 0 0 {name=M17
L=0.28u
W=0.5u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {lab_pin.sym} 1430 130 0 0 {name=p16 sig_type=std_logic lab=p1}
C {lab_pin.sym} 1430 230 0 0 {name=p17 sig_type=std_logic lab=vfb}
C {lab_pin.sym} 1480 180 0 1 {name=p18 sig_type=std_logic lab=vdd3v3}
C {symbols/pfet_03v3.sym} 1600 180 0 0 {name=M18
L=0.28u
W=0.5u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {lab_pin.sym} 1620 130 0 0 {name=p19 sig_type=std_logic lab=vfb}
C {lab_pin.sym} 1670 180 0 1 {name=p21 sig_type=std_logic lab=vdd3v3}
C {symbols/nfet_03v3.sym} 1060 300 0 0 {name=M19
L=0.28u
W=0.5u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {lab_pin.sym} 1030 330 0 0 {name=p20 sig_type=std_logic lab=vss}
C {symbols/nfet_03v3.sym} 1250 300 0 0 {name=M20
L=0.28u
W=0.5u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {lab_pin.sym} 580 160 0 1 {name=p22 sig_type=std_logic lab=n1}
C {lab_pin.sym} 1270 250 0 0 {name=p23 sig_type=std_logic lab=n1}
C {lab_wire.sym} 490 120 0 1 {name=p24 sig_type=std_logic lab=nb1}
C {symbols/nfet_03v3.sym} 1460 300 0 0 {name=M21
L=0.28u
W=0.5u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {lab_pin.sym} 1480 250 0 0 {name=p25 sig_type=std_logic lab=n1}
C {lab_pin.sym} 1530 300 0 1 {name=p26 sig_type=std_logic lab=vss}
C {lab_pin.sym} 1480 350 0 0 {name=p27 sig_type=std_logic lab=nb1}
C {symbols/nfet_03v3.sym} 1620 300 0 0 {name=M22
L=0.28u
W=0.5u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {lab_pin.sym} 1690 330 0 1 {name=p28 sig_type=std_logic lab=vss}
C {lab_pin.sym} 1640 250 0 0 {name=p29 sig_type=std_logic lab=nb1}
C {lab_wire.sym} 630 20 0 1 {name=p30 sig_type=std_logic lab=pb1}
C {lab_pin.sym} 730 -30 0 1 {name=p31 sig_type=std_logic lab=p2}
C {symbols/pfet_03v3.sym} 1240 430 0 0 {name=M23
L=0.28u
W=0.5u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {lab_pin.sym} 1260 380 0 0 {name=p32 sig_type=std_logic lab=p2}
C {symbols/pfet_03v3.sym} 1400 430 0 0 {name=M24
L=0.28u
W=0.5u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {lab_pin.sym} 1420 380 0 0 {name=p33 sig_type=std_logic lab=p2}
C {lab_pin.sym} 1420 480 0 0 {name=p34 sig_type=std_logic lab=pb1}
C {lab_pin.sym} 1470 430 0 1 {name=p35 sig_type=std_logic lab=vdd3v3}
C {symbols/pfet_03v3.sym} 1590 430 0 0 {name=M25
L=0.28u
W=0.5u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {lab_pin.sym} 1610 380 0 0 {name=p36 sig_type=std_logic lab=pb1}
C {lab_pin.sym} 1660 430 0 1 {name=p37 sig_type=std_logic lab=vdd3v3}
C {lab_pin.sym} 1220 460 0 0 {name=p38 sig_type=std_logic lab=vdd3v3}
C {symbols/cap_mim_2f0fF.sym} 100 10 2 1 {name=C3
W=10e-6
L=10e-6
model=cap_mim_2f0_m4m5_noshield
spiceprefix=X
m=4}
