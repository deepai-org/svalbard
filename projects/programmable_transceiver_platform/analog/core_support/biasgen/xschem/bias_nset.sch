v {xschem version=3.4.6 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
T {50nA} -200 -330 0 0 0.4 0.4 {}
N -120 60 -40 60 {
lab=nbias}
N -180 90 -180 110 {
lab=avss}
N -220 60 -180 60 {
lab=avss}
N -220 60 -220 110 {
lab=avss}
N -180 10 -180 30 {
lab=nbias}
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
N -180 -110 -180 -90 {
lab=ncasc}
N -140 -160 70 -160 {lab=ena}
N -180 10 -120 10 {lab=nbias}
N -180 -30 -180 10 {
lab=nbias}
N -120 10 -120 60 {lab=nbias}
N -140 60 -120 60 {
lab=nbias}
N -180 -110 -120 -110 {lab=ncasc}
N -180 -130 -180 -110 {
lab=ncasc}
N -120 -110 -120 -60 {lab=ncasc}
N -120 -60 -100 -60 {lab=ncasc}
N -140 -60 -120 -60 {lab=ncasc}
N 210 -40 240 -40 {lab=shld2}
N 210 -20 240 -20 {lab=shld3}
C {devices/iopin.sym} -110 110 0 0 {name=p4 lab=avss}
C {devices/ipin.sym} 70 -160 0 1 {name=p5 lab=ena}
C {devices/iopin.sym} -110 -280 0 0 {name=p2 lab=itail}
C {opin.sym} -40 60 0 0 {name=p3 lab=nbias}
C {opin.sym} -100 -60 0 0 {name=p8 lab=ncasc}
C {devices/iopin.sym} 210 -40 0 1 {name=p1 lab=shld2}
C {devices/iopin.sym} 210 -20 0 1 {name=p7 lab=shld3}
C {lab_pin.sym} 240 -40 0 1 {name=p10 sig_type=std_logic lab=shld2}
C {lab_pin.sym} 240 -20 0 1 {name=p11 sig_type=std_logic lab=shld3}
C {gf180mcu_fd_pr/nfet_05v0.sym} -160 60 0 1 {name=M1
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
C {gf180mcu_fd_pr/nfet_05v0.sym} -160 -160 0 1 {name=M3
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
