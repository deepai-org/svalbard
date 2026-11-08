v {xschem version=3.4.6 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
N 130 0 210 -0 {lab=#net1}
N 210 -0 210 90 {lab=#net1}
N -20 90 210 90 {lab=#net1}
N -20 30 -20 90 {lab=#net1}
N -20 30 10 30 {lab=#net1}
N -50 -30 10 -30 {lab=inp}
N -50 -0 10 0 {lab=ena}
N 60 50 60 120 {lab=bias}
N 30 120 60 120 {lab=bias}
N 80 40 80 120 {lab=vss}
N 80 120 110 120 {lab=vss}
N 80 -90 80 -40 {lab=vdd}
N 60 -90 80 -90 {lab=vdd}
N 210 -0 290 0 {lab=#net1}
C {se_folded_cascode_np_ab.sym} 160 0 0 0 {name=x1}
C {ipin.sym} -50 -30 0 0 {name=p1 lab=inp}
C {ipin.sym} -50 0 0 0 {name=p2 lab=ena}
C {iopin.sym} 30 120 0 1 {name=p3 lab=bias}
C {iopin.sym} 60 -90 0 1 {name=p4 lab=vdd}
C {iopin.sym} 110 120 0 0 {name=p5 lab=vss}
C {opin.sym} 290 0 0 0 {name=p6 lab=out}
