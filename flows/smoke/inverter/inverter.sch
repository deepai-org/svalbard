v {xschem version=3.4.8RC file_version=1.2

* SPDX-License-Identifier: Apache-2.0
* SVALBARD Chain 1 smoke-test inverter.
* Device sizes match gf180mcu_fd_sc_mcu7t5v0__inv_1 at the pinned candidate PDK revision.
}
G {}
K {}
V {}
S {}
E {}
N 720 -800 720 -760 {lab=VSS}
N 720 -1020 720 -980 {lab=VDD}
N 720 -950 880 -950 {lab=VNW}
N 720 -830 880 -830 {lab=VPW}
N 720 -890 720 -860 {lab=ZN}
N 660 -950 680 -950 {lab=I}
N 660 -890 660 -830 {lab=I}
N 660 -830 680 -830 {lab=I}
N 720 -890 880 -890 {lab=ZN}
N 660 -950 660 -890 {lab=I}
N 720 -920 720 -890 {lab=ZN}
N 560 -760 720 -760 {lab=VSS}
N 560 -890 660 -890 {lab=I}
N 560 -1020 720 -1020 {lab=VDD}
C {devices/ipin.sym} 560 -890 0 0 {name=p1 lab=I}
C {devices/opin.sym} 880 -890 0 0 {name=p2 lab=ZN}
C {devices/ipin.sym} 560 -1020 0 0 {name=p3 lab=VDD}
C {devices/ipin.sym} 880 -950 0 1 {name=p4 lab=VNW}
C {devices/ipin.sym} 880 -830 0 1 {name=p5 lab=VPW}
C {devices/ipin.sym} 560 -760 0 0 {name=p6 lab=VSS}
C {symbols/pfet_05v0.sym} 700 -950 0 0 {name=M1
L=0.5u
W=1.22u
nf=1
mult=1
ad="'int((nf+1)/2) * W/nf * 0.3u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.3u)'"
as="'int((nf+2)/2) * W/nf * 0.3u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.3u)'"
nrd="'0.3u / W'"
nrs="'0.3u / W'"
sa=0
sb=0
sd=0
model=pfet_05v0
spiceprefix=X
}
C {symbols/nfet_05v0.sym} 700 -830 0 0 {name=M2
L=0.6u
W=0.82u
nf=1
mult=1
ad="'int((nf+1)/2) * W/nf * 0.3u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.3u)'"
as="'int((nf+2)/2) * W/nf * 0.3u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.3u)'"
nrd="'0.3u / W'"
nrs="'0.3u / W'"
sa=0
sb=0
sd=0
model=nfet_05v0
spiceprefix=X
}
