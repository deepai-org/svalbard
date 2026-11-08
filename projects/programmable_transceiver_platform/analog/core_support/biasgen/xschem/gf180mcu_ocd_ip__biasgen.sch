v {xschem version=3.4.6 file_version=3.3}
G {}
K {}
V {}
S {}
E {}
T {dummy stacks on end (for improved matching)} 1430 630 0 0 0.3 0.3 {}
T {This bias generator is designed for the Chipalooza analog test chip, and has:
3 trimmable 1uA current sinks for the bandgap and voltage bias generator (9 control bits)
1 5-bit iDAC source for the voltage bias generator (5 control bits)
2 5-bit iDAC sources for the user projects (10 control bits)
} 200 -690 0 0 0.4 0.4 {}
N 550 -380 600 -380 {
lab=ena}
N 550 -360 600 -360 {
lab=ref_in}
N 550 -340 600 -340 {
lab=vbg}
N 550 -320 600 -320 {
lab=ref_sel_vbg}
N 550 -170 600 -170 {
lab=dvss}
N 550 -140 600 -140 {
lab=dvss}
N 900 -380 950 -380 {
lab=avdd}
N 900 -360 950 -360 {
lab=avss}
N 900 -340 950 -340 {
lab=dvdd}
N 900 -320 950 -320 {
lab=dvss}
N 900 -170 950 -170 {
lab=#net1}
N 900 -140 950 -140 {
lab=#net2}
N 910 -70 960 -70 {
lab=avdd}
N 910 -50 960 -50 {
lab=avss}
N 910 -30 960 -30 {
lab=dvdd}
N 910 -10 960 -10 {
lab=dvss}
N 480 -200 600 -200 {lab=pbias}
N 460 -220 460 850 {lab=pcasc}
N 460 -220 600 -220 {lab=pcasc}
N 440 -30 600 -30 {lab=nbias}
N 440 -240 440 -30 {lab=nbias}
N 440 -240 600 -240 {lab=nbias}
N 420 -10 600 -10 {lab=ncasc}
N 420 -260 420 -10 {lab=ncasc}
N 420 -260 600 -260 {lab=ncasc}
N 390 50 600 50 {lab=bandgap_sink1[2:0]}
N 440 150 600 150 {lab=nbias}
N 420 170 600 170 {lab=ncasc}
N 390 230 600 230 {lab=bandgap_sink2[1:0]}
N 440 -30 440 150 {lab=nbias}
N 420 -10 420 170 {lab=ncasc}
N 440 330 600 330 {lab=nbias}
N 420 350 600 350 {lab=ncasc}
N 390 410 600 410 {lab=voltgen_sink1[2:0]}
N 440 150 440 330 {lab=nbias}
N 420 170 420 350 {lab=ncasc}
N 440 330 440 510 {lab=nbias}
N 420 350 420 530 {lab=ncasc}
N 910 50 960 50 {lab=bandgap_sink1_ibias}
N 910 110 960 110 {
lab=avdd}
N 910 130 960 130 {
lab=avss}
N 910 150 960 150 {
lab=dvdd}
N 910 170 960 170 {
lab=dvss}
N 910 230 960 230 {lab=bandgap_sink2_ibias}
N 910 290 960 290 {
lab=avdd}
N 910 310 960 310 {
lab=avss}
N 910 330 960 330 {
lab=dvdd}
N 910 350 960 350 {
lab=dvss}
N 910 410 960 410 {lab=voltgen_sink1_ibias}
N 550 -280 600 -280 {lab=ref_sel_fine}
N 550 -300 600 -300 {lab=ref_sel_coarse}
N 910 830 960 830 {
lab=avdd}
N 910 850 960 850 {
lab=avss}
N 910 870 960 870 {
lab=dvdd}
N 910 890 960 890 {
lab=dvss}
N 910 950 960 950 {
lab=voltgen_source_ibias}
N 480 830 600 830 {lab=pbias}
N 460 850 600 850 {lab=pcasc}
N 390 950 600 950 {lab=voltgen_source[4:0]}
N 480 -200 480 830 {lab=pbias}
N 380 -260 420 -260 {lab=ncasc}
N 380 -240 440 -240 {lab=nbias}
N 380 -220 460 -220 {lab=pcasc}
N 380 -200 480 -200 {lab=pbias}
N 1400 740 1450 740 {lab=nbias}
N 1400 760 1450 760 {lab=ncasc}
N 1400 720 1450 720 {lab=avss}
N 1750 760 1780 760 {lab=avss}
N 1750 900 1790 900 {lab=#net3}
N 1750 860 1780 860 {lab=avdd}
N 1400 860 1450 860 {lab=pbias}
N 1400 880 1450 880 {lab=pcasc}
N 1400 900 1450 900 {lab=avdd}
N 1750 720 1780 720 {lab=#net4}
N 1780 830 1780 860 {lab=avdd}
N 1780 760 1780 790 {lab=avss}
N 1600 790 1780 790 {lab=avss}
N 1600 830 1780 830 {lab=avdd}
N 910 10 960 10 {
lab=avss}
N 910 30 960 30 {
lab=avss}
N 910 190 960 190 {
lab=avss}
N 910 210 960 210 {
lab=avss}
N 910 370 960 370 {
lab=avss}
N 910 390 960 390 {
lab=avss}
N 910 910 960 910 {lab=avdd}
N 910 930 960 930 {lab=avdd}
N 900 -300 950 -300 {lab=avdd}
N 910 470 960 470 {
lab=avdd}
N 910 490 960 490 {
lab=avss}
N 910 510 960 510 {
lab=dvdd}
N 910 530 960 530 {
lab=dvss}
N 440 510 600 510 {lab=nbias}
N 420 530 600 530 {lab=ncasc}
N 390 590 600 590 {lab=voltgen_sink2[2:0]}
N 910 590 960 590 {lab=voltgen_sink2_ibias}
N 910 550 960 550 {
lab=avss}
N 910 570 960 570 {
lab=avss}
N 910 1030 960 1030 {
lab=avdd}
N 910 1050 960 1050 {
lab=avss}
N 910 1070 960 1070 {
lab=dvdd}
N 910 1090 960 1090 {
lab=dvss}
N 910 1150 960 1150 {
lab=idac1_source_ibias}
N 480 1030 600 1030 {lab=pbias}
N 460 1050 600 1050 {lab=pcasc}
N 390 1150 600 1150 {lab=idac1_source[4:0]}
N 910 1110 960 1110 {lab=avdd}
N 910 1130 960 1130 {lab=avdd}
N 910 1230 960 1230 {
lab=avdd}
N 910 1250 960 1250 {
lab=avss}
N 910 1270 960 1270 {
lab=dvdd}
N 910 1290 960 1290 {
lab=dvss}
N 910 1350 960 1350 {
lab=idac2_source_ibias}
N 480 1230 600 1230 {lab=pbias}
N 460 1250 600 1250 {lab=pcasc}
N 390 1350 600 1350 {lab=idac2_source[4:0]}
N 910 1310 960 1310 {lab=avdd}
N 910 1330 960 1330 {lab=avdd}
N 460 850 460 1050 {lab=pcasc}
N 480 830 480 1030 {lab=pbias}
N 480 1030 480 1230 {lab=pbias}
N 460 1050 460 1250 {lab=pcasc}
C {bias_generator_fe.sym} 750 -160 0 0 {name=x1}
C {devices/iopin.sym} 950 -380 0 0 {name=p1 lab=avdd}
C {devices/iopin.sym} 950 -360 0 0 {name=p2 lab=avss}
C {devices/iopin.sym} 950 -340 0 0 {name=p3 lab=dvdd}
C {devices/iopin.sym} 950 -320 0 0 {name=p4 lab=dvss}
C {devices/lab_pin.sym} 960 -70 0 1 {name=p5 sig_type=std_logic lab=avdd}
C {devices/lab_pin.sym} 960 -50 0 1 {name=p6 sig_type=std_logic lab=avss}
C {devices/lab_pin.sym} 960 -30 0 1 {name=p7 sig_type=std_logic lab=dvdd}
C {devices/lab_pin.sym} 960 -10 0 1 {name=p8 sig_type=std_logic lab=dvss}
C {devices/ipin.sym} 550 -380 0 0 {name=p24 lab=ena}
C {devices/ipin.sym} 550 -360 0 0 {name=p25 lab=ref_in}
C {devices/ipin.sym} 550 -340 0 0 {name=p26 lab=vbg}
C {devices/ipin.sym} 550 -320 0 0 {name=p27 lab=ref_sel_vbg}
C {devices/noconn.sym} 950 -170 0 1 {name=l1}
C {devices/noconn.sym} 950 -140 0 1 {name=l2}
C {devices/lab_pin.sym} 550 -170 0 0 {name=p28 sig_type=std_logic lab=dvss}
C {devices/lab_pin.sym} 550 -140 0 0 {name=p29 sig_type=std_logic lab=dvss}
C {devices/ipin.sym} 390 50 0 0 {name=p31 lab=bandgap_sink1[2:0]}
C {devices/ipin.sym} 390 410 0 0 {name=p11 lab=voltgen_sink1[2:0]}
C {devices/ipin.sym} 390 590 0 0 {name=p13 lab=voltgen_sink2[2:0]}
C {devices/iopin.sym} 960 50 0 0 {name=p18 lab=bandgap_sink1_ibias}
C {devices/lab_pin.sym} 960 110 0 1 {name=p19 sig_type=std_logic lab=avdd}
C {devices/lab_pin.sym} 960 130 0 1 {name=p20 sig_type=std_logic lab=avss}
C {devices/lab_pin.sym} 960 150 0 1 {name=p21 sig_type=std_logic lab=dvdd}
C {devices/lab_pin.sym} 960 170 0 1 {name=p22 sig_type=std_logic lab=dvss}
C {devices/iopin.sym} 960 410 0 0 {name=p32 lab=voltgen_sink1_ibias}
C {devices/lab_pin.sym} 960 290 0 1 {name=p33 sig_type=std_logic lab=avdd}
C {devices/lab_pin.sym} 960 310 0 1 {name=p34 sig_type=std_logic lab=avss}
C {devices/lab_pin.sym} 960 330 0 1 {name=p35 sig_type=std_logic lab=dvdd}
C {devices/lab_pin.sym} 960 350 0 1 {name=p36 sig_type=std_logic lab=dvss}
C {devices/iopin.sym} 960 590 0 0 {name=p38 lab=voltgen_sink2_ibias}
C {devices/ipin.sym} 550 -280 0 0 {name=p51 lab=ref_sel_fine}
C {devices/ipin.sym} 550 -300 0 0 {name=p52 lab=ref_sel_coarse}
C {bias_generator_be0p.sym} 760 1130 0 0 {name=x13}
C {devices/lab_pin.sym} 960 830 0 1 {name=p53 sig_type=std_logic lab=avdd}
C {devices/lab_pin.sym} 960 850 0 1 {name=p54 sig_type=std_logic lab=avss}
C {devices/lab_pin.sym} 960 870 0 1 {name=p55 sig_type=std_logic lab=dvdd}
C {devices/lab_pin.sym} 960 890 0 1 {name=p56 sig_type=std_logic lab=dvss}
C {devices/iopin.sym} 960 950 0 0 {name=p63 lab=voltgen_source_ibias}
C {devices/ipin.sym} 390 950 0 0 {name=p85 lab=voltgen_source[4:0]}
C {bias_nstack.sym} 1600 740 0 0 {name=x8[4:0]}
C {bias_pstack.sym} 1600 900 0 0 {name=x9[4:0]}
C {lab_pin.sym} 380 -260 0 0 {name=p9 sig_type=std_logic lab=ncasc}
C {lab_pin.sym} 380 -240 0 0 {name=p10 sig_type=std_logic lab=nbias}
C {lab_pin.sym} 380 -220 0 0 {name=p12 sig_type=std_logic lab=pcasc}
C {lab_pin.sym} 380 -200 0 0 {name=p14 sig_type=std_logic lab=pbias}
C {lab_pin.sym} 1400 900 0 0 {name=p16 sig_type=std_logic lab=avdd}
C {lab_pin.sym} 1400 720 0 0 {name=p23 sig_type=std_logic lab=avss}
C {lab_pin.sym} 1780 760 0 1 {name=p30 sig_type=std_logic lab=avss}
C {lab_pin.sym} 1780 860 0 1 {name=p37 sig_type=std_logic lab=avdd}
C {lab_pin.sym} 1400 740 0 0 {name=p43 sig_type=std_logic lab=nbias}
C {lab_pin.sym} 1400 760 0 0 {name=p49 sig_type=std_logic lab=ncasc}
C {lab_pin.sym} 1400 860 0 0 {name=p58 sig_type=std_logic lab=pbias}
C {lab_pin.sym} 1400 880 0 0 {name=p64 sig_type=std_logic lab=pcasc}
C {devices/noconn.sym} 1780 720 0 1 {name=l3}
C {devices/noconn.sym} 1790 900 0 1 {name=l4}
C {devices/lab_pin.sym} 960 10 0 1 {name=p70 sig_type=std_logic lab=avss}
C {devices/lab_pin.sym} 960 30 0 1 {name=p81 sig_type=std_logic lab=avss}
C {devices/lab_pin.sym} 960 190 0 1 {name=p82 sig_type=std_logic lab=avss}
C {devices/lab_pin.sym} 960 210 0 1 {name=p84 sig_type=std_logic lab=avss}
C {devices/lab_pin.sym} 960 370 0 1 {name=p86 sig_type=std_logic lab=avss}
C {devices/lab_pin.sym} 960 390 0 1 {name=p88 sig_type=std_logic lab=avss}
C {devices/lab_pin.sym} 960 910 0 1 {name=p95 sig_type=std_logic lab=avdd}
C {devices/lab_pin.sym} 960 930 0 1 {name=p96 sig_type=std_logic lab=avdd}
C {lab_pin.sym} 950 -300 0 1 {name=p105 sig_type=std_logic lab=avdd}
C {bias_generator_ben1um.sym} 760 230 0 0 {name=x8}
C {bias_generator_ben1um.sym} 760 590 0 0 {name=x3}
C {devices/lab_pin.sym} 960 470 0 1 {name=p15 sig_type=std_logic lab=avdd}
C {devices/lab_pin.sym} 960 490 0 1 {name=p17 sig_type=std_logic lab=avss}
C {devices/lab_pin.sym} 960 510 0 1 {name=p39 sig_type=std_logic lab=dvdd}
C {devices/lab_pin.sym} 960 530 0 1 {name=p40 sig_type=std_logic lab=dvss}
C {devices/ipin.sym} 390 230 0 0 {name=p41 lab=bandgap_sink2[1:0]}
C {devices/iopin.sym} 960 230 0 0 {name=p42 lab=bandgap_sink2_ibias}
C {devices/lab_pin.sym} 960 550 0 1 {name=p44 sig_type=std_logic lab=avss}
C {devices/lab_pin.sym} 960 570 0 1 {name=p45 sig_type=std_logic lab=avss}
C {bias_generator_ben1um.sym} 760 770 0 0 {name=x4}
C {bias_generator_ben250nm.sym} 760 410 0 0 {name=x2}
C {bias_generator_be0p.sym} 760 1330 0 0 {name=x5}
C {devices/lab_pin.sym} 960 1030 0 1 {name=p46 sig_type=std_logic lab=avdd}
C {devices/lab_pin.sym} 960 1050 0 1 {name=p47 sig_type=std_logic lab=avss}
C {devices/lab_pin.sym} 960 1070 0 1 {name=p48 sig_type=std_logic lab=dvdd}
C {devices/lab_pin.sym} 960 1090 0 1 {name=p50 sig_type=std_logic lab=dvss}
C {devices/iopin.sym} 960 1150 0 0 {name=p57 lab=idac1_source_ibias}
C {devices/ipin.sym} 390 1150 0 0 {name=p59 lab=idac1_source[4:0]}
C {devices/lab_pin.sym} 960 1110 0 1 {name=p60 sig_type=std_logic lab=avdd}
C {devices/lab_pin.sym} 960 1130 0 1 {name=p61 sig_type=std_logic lab=avdd}
C {bias_generator_be0p.sym} 760 1530 0 0 {name=x6}
C {devices/lab_pin.sym} 960 1230 0 1 {name=p65 sig_type=std_logic lab=avdd}
C {devices/lab_pin.sym} 960 1250 0 1 {name=p66 sig_type=std_logic lab=avss}
C {devices/lab_pin.sym} 960 1270 0 1 {name=p67 sig_type=std_logic lab=dvdd}
C {devices/lab_pin.sym} 960 1290 0 1 {name=p68 sig_type=std_logic lab=dvss}
C {devices/iopin.sym} 960 1350 0 0 {name=p69 lab=idac2_source_ibias}
C {devices/ipin.sym} 390 1350 0 0 {name=p71 lab=idac2_source[4:0]}
C {devices/lab_pin.sym} 960 1310 0 1 {name=p72 sig_type=std_logic lab=avdd}
C {devices/lab_pin.sym} 960 1330 0 1 {name=p73 sig_type=std_logic lab=avdd}
