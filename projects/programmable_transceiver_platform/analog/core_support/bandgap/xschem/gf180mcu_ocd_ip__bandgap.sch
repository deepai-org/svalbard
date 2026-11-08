v {xschem version=3.4.6 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
N 360 260 510 260 {lab=vbg_unbuf}
N 690 260 710 260 {lab=vbg}
N 580 300 580 330 {lab=dvss}
N 580 330 600 330 {lab=dvss}
N 580 190 580 220 {lab=dvdd}
N 580 190 600 190 {lab=dvdd}
N 630 260 690 260 {lab=vbg}
N 560 310 560 380 {lab=ibias2_1u}
N 150 300 210 300 {lab=trim[15:0]}
N 150 240 210 240 {lab=dvdd}
N 150 360 210 360 {lab=dvss}
N 170 320 210 320 {lab=ibias1_250n}
N 170 320 170 400 {lab=ibias1_250n}
N 150 330 160 330 {lab=ena}
N 160 330 160 340 {lab=ena}
N 160 340 210 340 {lab=ena}
N 360 230 510 230 {lab=#net1}
C {bandgap_unbuffered.sym} 230 340 0 0 {name=x1}
C {lab_wire.sym} 450 260 0 0 {name=p7 sig_type=std_logic lab=vbg_unbuf}
C {lab_pin.sym} 600 190 0 1 {name=p4 sig_type=std_logic lab=dvdd}
C {lab_pin.sym} 600 330 0 1 {name=p8 sig_type=std_logic lab=dvss}
C {ipin.sym} 150 300 0 0 {name=p2 lab=trim[15:0]}
C {ipin.sym} 150 330 0 0 {name=p3 lab=ena}
C {opin.sym} 710 260 0 0 {name=p5 lab=vbg}
C {iopin.sym} 560 380 1 0 {name=p9 lab=ibias2_1u}
C {iopin.sym} 170 400 1 0 {name=p10 lab=ibias1_250n}
C {iopin.sym} 150 240 2 0 {name=p12 lab=dvdd}
C {iopin.sym} 150 360 2 0 {name=p13 lab=dvss}
C {gf180mcu_ocd_ip__classab_buffer.sym} 660 260 0 0 {name=x3}
