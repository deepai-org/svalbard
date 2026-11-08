v {xschem version=3.4.6 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
T {Testbench for simple POR} -350 -200 0 0 0.6 0.6 {}
N -40 30 -40 60 {lab=GND}
N -40 -110 -40 -70 {lab=vdd3v3}
N -380 60 -40 60 {lab=GND}
N -210 -30 -190 -30 {lab=vdd3v3}
N -210 -110 -210 -30 {lab=vdd3v3}
N -330 -10 -330 -0 {lab=vbg}
N -330 -10 -190 -10 {lab=vbg}
N -390 -110 -40 -110 {lab=vdd3v3}
N -380 -30 -380 60 {lab=GND}
N -380 -110 -380 -90 {lab=vdd3v3}
N 110 -30 150 -30 {lab=por}
N 110 -10 150 -10 {lab=porb}
N 110 10 150 10 {lab=porb_u}
C {devices/gnd.sym} -40 60 0 0 {name=l1 lab=GND}
C {devices/vsource.sym} -380 -60 0 0 {name=V1 value="PWL(0.0 0 100u 0 5m 3.3)"}
C {devices/opin.sym} -390 -110 0 1 {name=p1 lab=vdd3v3}
C {devices/opin.sym} 150 10 0 0 {name=p4 lab=porb_u}
C {devices/code_shown.sym} -380 310 0 0 {name=s2 only_toplevel=false value=".save all
.control
tran 1u 80m
plot V(vdd3v3) V(vbg) V(porb_u)
plot V(porb_u)+7 V(porb)+3.5 V(por)
.endc"}
C {por_3v3_regulated.sym} -40 -20 0 0 {name=x1}
C {devices/vsource.sym} -330 30 0 0 {name=V2 value="PWL(0.0 0 500u 0 2m 1.2)"}
C {code_shown.sym} -380 130 0 0 {name=s1 only_toplevel=false value=".include /usr/share/pdk/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /usr/share/pdk/gf180mcuD/libs.tech/ngspice/sm141064.spice typical
.lib /usr/share/pdk/gf180mcuD/libs.tech/ngspice/sm141064.spice res_typical
.lib /usr/share/pdk/gf180mcuD/libs.tech/ngspice/sm141064.spice diode_typical
.lib /usr/share/pdk/gf180mcuD/libs.tech/ngspice/sm141064.spice mimcap_typical
.include /usr/share/pdk/gf180mcuD/libs.ref/gf180mcu_as_sc_mcu7t3v3/spice/gf180mcu_as_sc_mcu7t3v3.spice"}
C {lab_wire.sym} -280 -10 0 0 {name=p2 sig_type=std_logic lab=vbg}
C {lab_wire.sym} -260 -110 0 0 {name=p3 sig_type=std_logic lab=vdd3v3}
C {devices/opin.sym} 150 -10 0 0 {name=p5 lab=porb}
C {devices/opin.sym} 150 -30 0 0 {name=p6 lab=por}
