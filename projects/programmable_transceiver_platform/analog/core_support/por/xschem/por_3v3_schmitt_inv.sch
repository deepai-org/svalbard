v {xschem version=3.4.6 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
T {Schmitt trigger inverter, 3.3V} -110 -210 0 0 0.4 0.4 {}
N 0 30 0 70 {lab=out}
N 0 130 0 160 {lab=#net1}
N -0 -70 0 -30 {lab=xxx}
N 0 -160 0 -130 {lab=vdd3v3}
N -0 220 0 250 {lab=vss}
N -70 100 -40 100 {lab=in}
N -70 0 -70 100 {lab=in}
N -70 -0 -40 -0 {lab=in}
N -130 50 -70 50 {lab=in}
N -0 50 210 50 {lab=out}
N -70 190 -40 190 {lab=in}
N -70 100 -70 190 {lab=in}
N -70 -100 -70 -0 {lab=in}
N -70 -100 -40 -100 {lab=in}
N 0 140 100 140 {lab=#net1}
N 130 50 130 100 {lab=out}
N 130 -10 130 50 {lab=out}
N 0 -50 100 -50 {lab=xxx}
N 160 -50 190 -50 {lab=vss}
N 160 140 190 140 {lab=vdd3v3}
N 130 -160 130 -50 {lab=vdd3v3}
N 0 -160 130 -160 {lab=vdd3v3}
N 0 250 130 250 {lab=vss}
N 130 140 130 250 {lab=vss}
N -0 100 60 100 {lab=vss}
N 60 100 60 250 {lab=vss}
N -0 190 60 190 {lab=vss}
N -0 -0 60 -0 {lab=vdd3v3}
N 60 -160 60 -0 {lab=vdd3v3}
N -0 -100 60 -100 {lab=vdd3v3}
C {symbols/nfet_03v3.sym} -20 100 0 0 {name=M1
L=0.28u
W=1.5u
nf=2
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
C {symbols/pfet_03v3.sym} -20 0 0 0 {name=M2
L=0.28u
W=0.75u
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
C {symbols/pfet_03v3.sym} -20 -100 0 0 {name=M3
L=0.28u
W=3u
nf=4
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
C {symbols/nfet_03v3.sym} -20 190 0 0 {name=M4
L=0.28u
W=1.5u
nf=2
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
C {symbols/nfet_03v3.sym} 130 120 3 1 {name=M5
L=0.56u
W=6u
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
C {symbols/pfet_03v3.sym} 130 -30 1 1 {name=M6
L=0.56u
W=3u
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
C {lab_pin.sym} 190 140 0 1 {name=p1 sig_type=std_logic lab=vdd3v3}
C {lab_pin.sym} 190 -50 0 1 {name=p2 sig_type=std_logic lab=vss}
C {iopin.sym} 0 -160 0 1 {name=p3 lab=vdd3v3}
C {iopin.sym} 0 250 0 1 {name=p4 lab=vss}
C {ipin.sym} -130 50 0 0 {name=p5 lab=in}
C {opin.sym} 210 50 0 0 {name=p6 lab=out}
C {lab_wire.sym} 40 -50 0 0 {name=p7 sig_type=std_logic lab=p1}
C {lab_wire.sym} 40 140 2 1 {name=p8 sig_type=std_logic lab=n1}
