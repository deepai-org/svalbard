v {xschem version=3.4.6 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
T {Simple transconductance amp for POR voltage setting.} -50 -180 0 0 0.4 0.4 {}
N 140 -20 140 20 {lab=#net1}
N 320 -20 320 20 {lab=out}
N 140 50 320 50 {lab=vss}
N 140 80 140 100 {lab=nc}
N 140 100 320 100 {lab=nc}
N 320 80 320 100 {lab=nc}
N 60 50 100 50 {lab=inp}
N 140 -120 140 -80 {lab=vdd3v3}
N 140 -120 320 -120 {lab=vdd3v3}
N 320 -120 320 -80 {lab=vdd3v3}
N 180 -50 280 -50 {lab=#net1}
N 320 -10 430 -10 {lab=out}
N 140 -0 230 -0 {lab=#net1}
N 230 -50 230 -0 {lab=#net1}
N 230 100 230 120 {lab=nc}
N 230 180 230 210 {lab=#net2}
N 230 270 230 310 {lab=vss}
N 140 150 190 150 {lab=ena}
N 230 310 280 310 {lab=vss}
N 280 50 280 310 {lab=vss}
N 230 240 280 240 {lab=vss}
N 230 150 280 150 {lab=vss}
N 360 50 430 50 {lab=inn}
N 80 -50 140 -50 {lab=vdd3v3}
N 80 -120 80 -50 {lab=vdd3v3}
N 320 -50 380 -50 {lab=vdd3v3}
N 380 -120 380 -50 {lab=vdd3v3}
N 320 -120 380 -120 {lab=vdd3v3}
N 130 240 190 240 {lab=nbias}
N 100 310 230 310 {lab=vss}
N 50 -120 140 -120 {lab=vdd3v3}
N 630 -90 680 -90 {lab=vdd3v3}
N 680 -120 680 -90 {lab=vdd3v3}
N 630 -120 680 -120 {lab=vdd3v3}
N 630 -60 680 -60 {lab=vdd3v3}
N 680 -90 680 -60 {lab=vdd3v3}
N 570 -90 590 -90 {lab=vdd3v3}
N 570 -120 570 -90 {lab=vdd3v3}
N 570 -120 630 -120 {lab=vdd3v3}
N 620 280 620 300 {lab=vss}
N 580 300 620 300 {lab=vss}
N 580 250 580 300 {lab=vss}
N 580 220 580 250 {lab=vss}
N 580 220 680 220 {lab=vss}
N 680 220 680 250 {lab=vss}
N 620 250 680 250 {lab=vss}
N 780 280 780 300 {lab=vss}
N 740 300 780 300 {lab=vss}
N 740 250 740 300 {lab=vss}
N 780 250 840 250 {lab=vss}
N 840 250 840 300 {lab=vss}
N 780 300 840 300 {lab=vss}
N 780 190 780 220 {lab=n1}
C {symbols/pfet_03v3.sym} 300 -50 0 0 {name=M1
L=0.28u
W=6u
nf=6
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
C {symbols/pfet_03v3.sym} 160 -50 0 1 {name=M2
L=0.28u
W=6u
nf=6
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
C {symbols/nfet_03v3.sym} 120 50 0 0 {name=M3
L=0.28u
W=12u
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
C {symbols/nfet_03v3.sym} 340 50 0 1 {name=M4
L=0.28u
W=12u
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
C {symbols/nfet_03v3.sym} 210 150 0 0 {name=M5
L=0.28u
W=12u
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
C {symbols/nfet_03v3.sym} 210 240 0 0 {name=M6
L=0.28u
W=12u
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
C {ipin.sym} 140 150 0 0 {name=p1 lab=ena}
C {ipin.sym} 60 50 0 0 {name=p3 lab=inp}
C {ipin.sym} 430 50 0 1 {name=p4 lab=inn}
C {opin.sym} 430 -10 0 0 {name=p2 lab=out}
C {iopin.sym} 50 -120 0 1 {name=p5 lab=vdd3v3}
C {iopin.sym} 100 310 0 1 {name=p6 lab=vss}
C {ipin.sym} 130 240 0 0 {name=p7 lab=nbias}
C {symbols/pfet_03v3.sym} 610 -90 0 0 {name=M7
L=0.28u
W=4u
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
C {lab_pin.sym} 570 -120 0 0 {name=p8 sig_type=std_logic lab=vdd3v3}
C {symbols/nfet_03v3.sym} 600 250 0 0 {name=M8
L=0.28u
W=2u
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
C {lab_pin.sym} 580 300 0 0 {name=p9 sig_type=std_logic lab=vss}
C {symbols/nfet_03v3.sym} 760 250 0 0 {name=M9
L=0.28u
W=2u
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
C {lab_pin.sym} 740 300 0 0 {name=p11 sig_type=std_logic lab=vss}
C {lab_pin.sym} 780 190 0 0 {name=p12 sig_type=std_logic lab=nc}
C {lab_pin.sym} 320 100 0 1 {name=p13 sig_type=std_logic lab=nc}
