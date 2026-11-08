v {xschem version=3.4.6 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
T {step down 16x} 470 280 0 0 0.4 0.4 {}
T {step down 16x} 360 -250 0 0 0.4 0.4 {}
T {step down 20x} 650 -250 0 0 0.4 0.4 {}
T {512nA} 270 -220 0 0 0.3 0.3 {}
T {32nA} 410 -220 0 0 0.3 0.3 {}
T {2nA} 560 -220 0 0 0.3 0.3 {}
T {100pA} 710 -220 0 0 0.3 0.3 {}
T {POR with 40ms reset delay} -130 -340 0 0 0.5 0.5 {}
N -110 -10 0 -10 {lab=ena}
N 170 -20 250 -20 {lab=vpb}
N 70 -180 290 -180 {lab=vdd3v3}
N -110 -180 70 -180 {lab=vdd3v3}
N 70 50 70 260 {lab=vss}
N 290 -180 900 -180 {lab=vdd3v3}
N 70 260 900 260 {lab=vss}
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
N 430 -40 430 -0 {lab=#net2}
N 430 60 430 90 {lab=#net3}
N 430 150 430 180 {lab=#net4}
N 430 240 430 260 {lab=vss}
N 380 120 430 120 {lab=vss}
N 380 120 380 260 {lab=vss}
N 380 210 430 210 {lab=vss}
N 430 70 470 70 {lab=#net3}
N 470 70 470 120 {lab=#net3}
N 430 160 470 160 {lab=#net4}
N 470 160 470 210 {lab=#net4}
N 470 210 540 210 {lab=#net4}
N 470 120 540 120 {lab=#net3}
N -30 110 290 110 {lab=vfb}
N 580 150 580 180 {lab=#net5}
N 580 240 580 260 {lab=vss}
N 580 120 650 120 {lab=vss}
N 650 120 650 260 {lab=vss}
N 580 210 650 210 {lab=vss}
N 430 30 490 30 {lab=vdd3v3}
N 490 -70 490 30 {lab=vdd3v3}
N 580 -50 580 -10 {lab=#net6}
N 580 50 580 90 {lab=#net7}
N 580 -30 620 -30 {lab=#net6}
N 620 -80 620 -30 {lab=#net6}
N 580 70 620 70 {lab=#net7}
N 620 20 620 70 {lab=#net7}
N 620 20 690 20 {lab=#net7}
N 620 -80 690 -80 {lab=#net6}
N 730 -50 730 -10 {lab=#net8}
N 730 -80 790 -80 {lab=vdd3v3}
N 730 20 790 20 {lab=vdd3v3}
N 790 -80 790 20 {lab=vdd3v3}
N 730 50 730 90 {lab=vcap}
N 220 70 250 70 {lab=vfb}
N 520 20 580 20 {lab=vdd3v3}
N 520 -80 580 -80 {lab=vdd3v3}
N 730 150 730 260 {lab=vss}
N 730 70 830 70 {lab=vcap}
N 900 140 900 260 {lab=vss}
N 1020 70 1070 70 {lab=porb_unbuf}
N -50 -70 -50 70 {lab=vbg}
N -140 260 70 260 {lab=vss}
N -100 160 -100 260 {lab=vss}
N -50 210 -50 260 {lab=vss}
N -100 -10 -100 100 {lab=ena}
N -50 70 -50 150 {lab=vbg}
N 290 190 290 260 {lab=vss}
N 790 -180 790 -80 {lab=vdd3v3}
N 900 -180 900 -0 {lab=vdd3v3}
N 520 -180 520 20 {lab=vdd3v3}
N 490 -180 490 -70 {lab=vdd3v3}
N 360 -180 360 70 {lab=vdd3v3}
N 70 -180 70 -90 {lab=vdd3v3}
N 730 -120 730 -110 {lab=#net9}
N 580 -120 580 -110 {lab=#net10}
N 430 -120 430 -100 {lab=#net11}
N 290 -120 290 -50 {lab=#net12}
N -110 -70 -50 -70 {lab=vbg}
N -30 -70 -30 110 {lab=vfb}
N -30 -70 -0 -70 {lab=vfb}
N -50 30 -0 30 {lab=vbg}
N 220 70 220 110 {lab=vfb}
N 1180 -50 1340 -50 {lab=porb}
N 1300 20 1340 20 {lab=por}
N 1190 20 1220 20 {lab=#net13}
N 1040 20 1110 20 {lab=porb_unbuf}
N 1040 20 1040 70 {lab=porb_unbuf}
N 1040 -50 1040 20 {lab=porb_unbuf}
N 1040 -50 1100 -50 {lab=porb_unbuf}
C {por_amp.sym} 80 -20 0 0 {name=x1}
C {por_3v3_schmitt_inv.sym} 920 70 0 0 {name=x2}
C {ipin.sym} -110 -10 0 0 {name=p1 lab=ena}
C {ipin.sym} -110 -70 0 0 {name=p2 lab=vbg}
C {symbols/nfet_03v3.sym} 450 120 0 1 {name=M1
L=0.28u
W=8u
nf=16
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
W=8.0u
nf=16
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
C {iopin.sym} -110 -180 0 1 {name=p3 lab=vdd3v3}
C {iopin.sym} -140 260 0 1 {name=p4 lab=vss}
C {symbols/ppolyf_u_1k.sym} 290 160 0 0 {name=R1
W=1e-6
L=2500e-6
model=ppolyf_u_1k
spiceprefix=X
m=1}
C {symbols/pfet_03v3.sym} 270 70 0 0 {name=M3
L=0.28u
W=8u
nf=16
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
W=8u
nf=16
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
W=10u
nf=20
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
W=10u
nf=20
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
C {symbols/cap_mim_2f0fF.sym} 730 120 0 0 {name=C1
W=10e-6
L=10e-6
model=cap_mim_2f0_m4m5_noshield
spiceprefix=X
m=8}
C {opin.sym} 1070 70 0 0 {name=p5 lab=porb_unbuf}
C {symbols/diode_nd2ps_03v3.sym} -100 130 2 0 {name=D1
model=diode_nd2ps_03v3
r_w=1u
r_l=1u
m=1}
C {symbols/diode_nd2ps_03v3.sym} -50 180 2 1 {name=D2
model=diode_nd2ps_03v3
r_w=1u
r_l=1u
m=1}
C {lab_wire.sym} 810 70 0 0 {name=p6 sig_type=std_logic lab=vcap}
C {ammeter.sym} 290 -150 0 0 {name=Vmeas savecurrent=true spice_ignore=0}
C {ammeter.sym} 430 -150 0 0 {name=Vmeas1 savecurrent=true spice_ignore=0}
C {ammeter.sym} 580 -150 0 0 {name=Vmeas2 savecurrent=true spice_ignore=0}
C {ammeter.sym} 730 -150 0 0 {name=Vmeas3 savecurrent=true spice_ignore=0}
C {lab_wire.sym} 180 110 0 0 {name=p7 sig_type=std_logic lab=vfb}
C {lab_wire.sym} 210 -20 0 0 {name=p8 sig_type=std_logic lab=vpb}
C {fillcap_4.sym} 1160 -130 0 0 {name=x3[1:0] VDD=vdd3v3 VNW=vdd3v3 VPW=vss VSS=vss prefix=gf180mcu_as_sc_mcu7t3v3__ }
C {tap_2.sym} 1160 -180 0 0 {name=x4 VSS=vss VDD=vdd3v3 prefix=gf180mcu_as_sc_mcu7t3v3__ }
C {buff_12.sym} 1140 -50 0 0 {name=x5 VDD=vdd3v3 VNW=vdd3v3 VPW=vss VSS=vss prefix=gf180mcu_as_sc_mcu7t3v3__ }
C {inv_4.sym} 1150 20 0 0 {name=x6 VDD=vdd3v3 VNW=vdd3v3 VPW=vss VSS=vss prefix=gf180mcu_as_sc_mcu7t3v3__ }
C {buff_12.sym} 1260 20 0 0 {name=x3 VDD=vdd3v3 VNW=vdd3v3 VPW=vss VSS=vss prefix=gf180mcu_as_sc_mcu7t3v3__ }
C {opin.sym} 1340 20 0 0 {name=p9 lab=por}
C {opin.sym} 1340 -50 0 0 {name=p10 lab=porb}
