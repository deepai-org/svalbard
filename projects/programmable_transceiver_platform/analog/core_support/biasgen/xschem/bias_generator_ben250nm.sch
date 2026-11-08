v {xschem version=3.4.6 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
T {Each bias_nstack is a 250nA unit current sink.
This circuit is designed to generate 250nA output with trim.
sink_ena[0] enables the base 250nA current
sink_ena[1] enables the trim 250nA current
For the nominal untrimmed output of 1uA, use sink_ena[1:0] = 2'b01} -2250 200 0 0 0.4 0.4 {}
T {Bias generator back-end for gf180mcu_ocd_openframe} -2250 130 0 0 0.6 0.6 {}
T {Dummy stacks used to fill out the area underneath the level shifters
in the layout, to keep continuity in the current sources for better
matching.} -1150 300 0 0 0.4 0.4 {}
N -2190 590 -2150 590 {
lab=dvdd}
N -2190 620 -2150 620 {
lab=dvss}
N -2190 420 -2150 420 {lab=nbias}
N -2190 440 -2150 440 {lab=ncasc}
N -2190 550 -2150 550 {lab=avss}
N -2190 520 -2150 520 {lab=avdd}
N -1070 730 -1020 730 {lab=nbias}
N -1070 830 -1020 830 {lab=nbias}
N -1050 850 -1020 850 {lab=ncasc}
N -1050 750 -1020 750 {lab=ncasc}
N -1100 710 -1020 710 {lab=sink_ena_5v0[1]}
N -1100 810 -1020 810 {lab=sink_ena_5v0[0]}
N -720 850 -680 850 {lab=avss}
N -720 750 -680 750 {lab=avss}
N -720 810 -580 810 {lab=sink_ibias}
N -720 710 -580 710 {lab=sink_ibias}
N -1700 670 -1650 670 {
lab=sink_ena_5v0[1:0]}
N -2030 690 -2000 690 {lab=sink_ena[1:0]}
N -1920 670 -1850 670 {lab=#net1}
N -2000 710 -2000 740 {lab=sink_ena[1:0]}
N -2000 670 -2000 690 {lab=sink_ena[1:0]}
N -2000 710 -1900 710 {lab=sink_ena[1:0]}
N -2000 690 -2000 710 {lab=sink_ena[1:0]}
N -1900 690 -1900 710 {lab=sink_ena[1:0]}
N -1900 690 -1850 690 {lab=sink_ena[1:0]}
N -1050 850 -1050 910 {lab=ncasc}
N -1070 830 -1070 910 {lab=nbias}
N -580 710 -580 810 {lab=sink_ibias}
N -1070 730 -1070 830 {lab=nbias}
N -1050 750 -1050 850 {lab=ncasc}
N -680 750 -680 850 {lab=avss}
N -680 850 -680 910 {lab=avss}
N -910 780 -870 780 {lab=shld2}
N -850 780 -810 780 {lab=shld3}
N -910 880 -870 880 {lab=shld2}
N -850 880 -810 880 {lab=shld3}
N -880 930 -850 930 {lab=shld2}
N -880 960 -850 960 {lab=shld3}
N -1070 480 -1020 480 {lab=nbias}
N -1050 500 -1020 500 {lab=ncasc}
N -1100 460 -1020 460 {lab=avss}
N -720 500 -680 500 {lab=avss}
N -720 460 -580 460 {lab=dummy_bias}
N -910 530 -870 530 {lab=shld2}
N -850 530 -810 530 {lab=shld3}
C {devices/iopin.sym} -2190 550 0 1 {name=p39 lab=avss}
C {devices/iopin.sym} -2190 520 0 1 {name=p42 lab=avdd}
C {devices/iopin.sym} -2190 590 0 1 {name=p98 lab=dvdd}
C {devices/iopin.sym} -2190 620 0 1 {name=p99 lab=dvss}
C {devices/lab_pin.sym} -2150 590 0 1 {name=p1 sig_type=std_logic lab=dvdd}
C {devices/lab_pin.sym} -2150 620 0 1 {name=p2 sig_type=std_logic lab=dvss}
C {devices/ipin.sym} -2190 420 0 0 {name=p5 lab=nbias}
C {fillcap_4.sym} -1900 820 0 0 {name=x7[1:0] VDD=dvdd VNW=dvdd VPW=dvss VSS=dvss prefix=gf180mcu_as_sc_mcu7t3v3__ }
C {diode_2.sym} -1910 740 0 0 {name=x6[1:0] VDD=dvdd VNW=dvdd VPW=dvss VSS=dvss prefix=gf180mcu_as_sc_mcu7t3v3__ }
C {devices/ipin.sym} -2190 440 0 0 {name=p155 lab=ncasc}
C {lab_pin.sym} -2150 420 0 1 {name=p6 sig_type=std_logic lab=nbias}
C {lab_pin.sym} -2150 440 0 1 {name=p7 sig_type=std_logic lab=ncasc}
C {lab_pin.sym} -2150 550 0 1 {name=p9 sig_type=std_logic lab=avss}
C {lab_pin.sym} -2150 520 0 1 {name=p41 sig_type=std_logic lab=avdd}
C {bias_nstack.sym} -870 730 0 0 {name=x2}
C {bias_nstack.sym} -870 830 0 0 {name=x3}
C {lab_pin.sym} -1050 910 3 0 {name=p23 sig_type=std_logic lab=ncasc}
C {lab_pin.sym} -1070 910 3 0 {name=p24 sig_type=std_logic lab=nbias}
C {lab_wire.sym} -1100 710 0 0 {name=p26 sig_type=std_logic lab=sink_ena_5v0[1]}
C {lab_wire.sym} -1100 810 0 0 {name=p30 sig_type=std_logic lab=sink_ena_5v0[0]}
C {lab_pin.sym} -680 910 1 1 {name=p33 sig_type=std_logic lab=avss}
C {devices/iopin.sym} -580 710 0 0 {name=p12 lab=sink_ibias}
C {devices/ipin.sym} -2030 690 0 0 {name=p13 lab=sink_ena[1:0]}
C {level_shift_5v.sym} -1700 710 0 0 {name=x4[1:0] vdd=avdd vss=avss }
C {inv_2.sym} -1960 670 0 0 {name=x5[1:0] VDD=dvdd VNW=dvdd VPW=dvss VSS=dvss prefix=gf180mcu_as_sc_mcu7t3v3__ }
C {lab_pin.sym} -1650 670 0 1 {name=p17 sig_type=std_logic lab=sink_ena_5v0[1:0]}
C {lab_pin.sym} -910 780 0 0 {name=p8 sig_type=std_logic lab=shld2}
C {lab_pin.sym} -810 780 0 1 {name=p10 sig_type=std_logic lab=shld3}
C {lab_pin.sym} -910 880 0 0 {name=p35 sig_type=std_logic lab=shld2}
C {lab_pin.sym} -810 880 0 1 {name=p36 sig_type=std_logic lab=shld3}
C {devices/iopin.sym} -880 930 0 1 {name=p37 lab=shld2}
C {devices/iopin.sym} -880 960 0 1 {name=p38 lab=shld3}
C {lab_pin.sym} -850 930 0 1 {name=p40 sig_type=std_logic lab=shld2}
C {lab_pin.sym} -850 960 0 1 {name=p43 sig_type=std_logic lab=shld3}
C {bias_nstack.sym} -870 480 0 0 {name=x1[7:0]}
C {lab_pin.sym} -910 530 0 0 {name=p15 sig_type=std_logic lab=shld2}
C {lab_pin.sym} -810 530 0 1 {name=p16 sig_type=std_logic lab=shld3}
C {lab_pin.sym} -580 460 0 1 {name=p4 sig_type=std_logic lab=dummy_bias}
C {lab_pin.sym} -680 500 1 1 {name=p18 sig_type=std_logic lab=avss}
C {lab_pin.sym} -1050 500 3 0 {name=p19 sig_type=std_logic lab=ncasc}
C {lab_pin.sym} -1070 480 3 0 {name=p20 sig_type=std_logic lab=nbias}
C {lab_pin.sym} -1100 460 1 1 {name=p3 sig_type=std_logic lab=avss}
C {tap_2.sym} -1900 890 0 0 {name=x2[1:0] VSS=dvss VDD=dvdd prefix=gf180mcu_as_sc_mcu7t3v3__ }
