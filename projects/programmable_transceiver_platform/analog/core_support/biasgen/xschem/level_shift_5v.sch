v {xschem version=3.4.6 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
N 540 -520 760 -520 { lab=vss}
N 760 -560 760 -520 { lab=vss}
N 520 -590 540 -590 { lab=vss}
N 540 -590 540 -520 { lab=vss}
N 760 -590 780 -590 { lab=vss}
N 780 -590 780 -520 { lab=vss}
N 760 -520 780 -520 { lab=vss}
N 700 -590 720 -590 { lab=in_n}
N 460 -590 480 -590 { lab=in_p}
N 520 -800 520 -780 { lab=vdd}
N 620 -800 760 -800 { lab=vdd}
N 760 -800 760 -780 { lab=vdd}
N 620 -820 620 -800 { lab=vdd}
N 760 -750 780 -750 { lab=vdd}
N 780 -800 780 -750 { lab=vdd}
N 760 -800 780 -800 { lab=vdd}
N 700 -750 720 -750 { lab=#net1}
N 760 -680 900 -680 { lab=S1_N}
N 900 -750 900 -680 { lab=S1_N}
N 900 -750 920 -750 { lab=S1_N}
N 780 -800 960 -800 { lab=vdd}
N 960 -800 960 -780 { lab=vdd}
N 900 -680 900 -590 { lab=S1_N}
N 900 -590 920 -590 { lab=S1_N}
N 960 -680 960 -620 { lab=S2_N}
N 960 -560 960 -520 { lab=vss}
N 780 -520 960 -520 { lab=vss}
N 960 -750 980 -750 { lab=vdd}
N 980 -800 980 -750 { lab=vdd}
N 960 -800 980 -800 { lab=vdd}
N 960 -590 980 -590 { lab=vss}
N 980 -590 980 -520 { lab=vss}
N 960 -520 980 -520 { lab=vss}
N 1080 -750 1080 -680 { lab=S2_N}
N 1080 -750 1100 -750 { lab=S2_N}
N 1140 -800 1140 -780 { lab=vdd}
N 1080 -680 1080 -590 { lab=S2_N}
N 1080 -590 1100 -590 { lab=S2_N}
N 1140 -560 1140 -520 { lab=vss}
N 1140 -750 1160 -750 { lab=vdd}
N 1160 -800 1160 -750 { lab=vdd}
N 1140 -800 1160 -800 { lab=vdd}
N 1140 -590 1160 -590 { lab=vss}
N 1160 -590 1160 -520 { lab=vss}
N 1140 -520 1160 -520 { lab=vss}
N 980 -800 1140 -800 { lab=vdd}
N 980 -520 1140 -520 { lab=vss}
N 960 -680 1080 -680 { lab=S2_N}
N 520 -560 520 -520 { lab=vss}
N 520 -520 540 -520 { lab=vss}
N 520 -800 620 -800 { lab=vdd}
N 760 -660 760 -620 { lab=S1_N}
N 520 -660 520 -620 { lab=#net1}
N 760 -720 760 -680 { lab=S1_N}
N 960 -720 960 -680 { lab=S2_N}
N 610 -750 700 -660 {lab=S1_N}
N 560 -750 610 -750 {lab=S1_N}
N 700 -660 760 -660 {lab=S1_N}
N 760 -680 760 -660 { lab=S1_N}
N 610 -660 700 -750 {lab=#net1}
N 520 -660 610 -660 {lab=#net1}
N 520 -720 520 -660 { lab=#net1}
N 470 -750 520 -750 {lab=vdd}
N 470 -800 470 -750 {lab=vdd}
N 470 -800 520 -800 {lab=vdd}
N 1140 -680 1140 -620 { lab=out}
N 1140 -680 1190 -680 {lab=out}
N 1140 -720 1140 -680 { lab=out}
C {devices/ipin.sym} 270 -880 0 0 {name=p6 lab=in_n}
C {devices/ipin.sym} 270 -850 0 0 {name=p5 lab=in_p}
C {devices/lab_wire.sym} 620 -820 0 0 {name=l1 sig_type=std_logic lab=vdd}
C {devices/lab_wire.sym} 660 -520 0 0 {name=l2 sig_type=std_logic lab=vss}
C {devices/lab_wire.sym} 460 -590 0 0 {name=l3 sig_type=std_logic lab=in_p}
C {devices/lab_wire.sym} 700 -590 0 0 {name=l4 sig_type=std_logic lab=in_n}
C {devices/lab_wire.sym} 1190 -680 0 1 {name=l9 sig_type=std_logic lab=out}
C {devices/lab_wire.sym} 860 -680 0 0 {name=l18 sig_type=std_logic lab=S1_N
}
C {devices/lab_wire.sym} 1040 -680 0 0 {name=l19 sig_type=std_logic lab=S2_N}
C {devices/opin.sym} 250 -770 0 0 {name=p4 lab=out}
C {gf180mcu_fd_pr/nfet_05v0.sym} 500 -590 0 0 {name=M8
L=0.6u
W=4.0u
nf=1
m=2
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_05v0
spiceprefix=X
}
C {gf180mcu_fd_pr/pfet_05v0.sym} 540 -750 0 1 {name=M10
L=0.5u
W=1.0u
nf=1
m=2
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_05v0
spiceprefix=X
}
C {gf180mcu_fd_pr/pfet_05v0.sym} 1120 -750 0 0 {name=M2
L=0.5u
W=2.0u
nf=1
m=4
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_05v0
spiceprefix=X
}
C {gf180mcu_fd_pr/pfet_05v0.sym} 740 -750 0 0 {name=M9
L=0.5u
W=1.0u
nf=1
m=2
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_05v0
spiceprefix=X
}
C {gf180mcu_fd_pr/pfet_05v0.sym} 940 -750 0 0 {name=M4
L=0.5u
W=2.0u
nf=1
m=2
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_05v0
spiceprefix=X
}
C {gf180mcu_fd_pr/nfet_05v0.sym} 740 -590 0 0 {name=M1
L=0.6u
W=4.0u
nf=1
m=2
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_05v0
spiceprefix=X
}
C {gf180mcu_fd_pr/nfet_05v0.sym} 940 -590 0 0 {name=M3
L=0.6u
W=1.0u
nf=1
m=2
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_05v0
spiceprefix=X
}
C {gf180mcu_fd_pr/nfet_05v0.sym} 1120 -590 0 0 {name=M5
L=0.6u
W=1.0u
nf=1
m=4
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_05v0
spiceprefix=X
}
