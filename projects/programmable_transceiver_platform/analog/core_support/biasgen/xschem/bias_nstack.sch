v {xschem version=3.4.6 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
T {50nA} -200 -330 0 0 0.4 0.4 {}
N -140 60 -40 60 {
lab=nbias}
N -180 90 -180 110 {
lab=avss}
N -220 60 -180 60 {
lab=avss}
N -220 60 -220 110 {
lab=avss}
N -180 -30 -180 30 {
lab=#net1}
N -220 -60 -180 -60 {
lab=avss}
N -220 -60 -220 60 {
lab=avss}
N -220 -160 -180 -160 {
lab=avss}
N -220 -160 -220 -60 {
lab=avss}
N -180 -280 -180 -190 {
lab=itail}
N -220 110 -180 110 {
lab=avss}
N -180 110 -110 110 {
lab=avss}
N -180 -280 -110 -280 {
lab=itail}
N -180 -130 -180 -90 {
lab=#net2}
N -140 -160 70 -160 {lab=ena}
N -140 -60 -120 -60 {lab=ncasc}
N 260 -250 300 -250 {lab=shld2}
N 260 -220 300 -220 {lab=shld3}
C {devices/iopin.sym} -110 110 0 0 {name=p4 lab=avss}
C {devices/ipin.sym} 70 -160 0 1 {name=p5 lab=ena}
C {devices/ipin.sym} -40 60 0 1 {name=p1 lab=nbias}
C {devices/iopin.sym} -110 -280 0 0 {name=p2 lab=itail}
C {devices/ipin.sym} -120 -60 0 1 {name=p7 lab=ncasc}
C {devices/iopin.sym} 260 -250 0 1 {name=p6 lab=shld2}
C {devices/iopin.sym} 260 -220 0 1 {name=p8 lab=shld3}
C {lab_pin.sym} 300 -250 0 1 {name=p10 sig_type=std_logic lab=shld2}
C {lab_pin.sym} 300 -220 0 1 {name=p11 sig_type=std_logic lab=shld3}
C {gf180mcu_fd_pr/nfet_05v0.sym} -160 -160 0 1 {name=M1
L=1.0u
W=3.0u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_05v0
spiceprefix=X
}
C {gf180mcu_fd_pr/nfet_05v0.sym} -160 -60 0 1 {name=M2
L=1.0u
W=3.0u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_05v0
spiceprefix=X
}
C {gf180mcu_fd_pr/nfet_05v0.sym} -160 60 0 1 {name=M3
L=1.0u
W=3.0u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_05v0
spiceprefix=X
}
