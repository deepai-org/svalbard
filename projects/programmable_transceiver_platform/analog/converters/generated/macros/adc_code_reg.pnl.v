module adc_code_reg (done,
    done_o,
    en,
    overload,
    VDD,
    VSS,
    bp,
    code_tc);
 input done;
 output done_o;
 input en;
 output overload;
 inout VDD;
 inout VSS;
 input [9:0] bp;
 output [9:0] code_tc;

 wire _00_;
 wire _01_;
 wire _02_;
 wire _03_;
 wire _04_;
 wire _05_;
 wire _06_;
 wire _07_;

 gf180mcu_fd_sc_mcu7t5v0__fillcap_32 FILLER_0_104 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_32 FILLER_0_138 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_16 FILLER_0_172 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_32 FILLER_0_2 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_32 FILLER_0_36 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_32 FILLER_0_70 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_32 FILLER_10_104 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_32 FILLER_10_138 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_16 FILLER_10_172 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_32 FILLER_10_2 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_32 FILLER_10_36 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_32 FILLER_10_70 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_16 FILLER_1_120 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_4 FILLER_1_136 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_32 FILLER_1_142 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_8 FILLER_1_174 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_4 FILLER_1_18 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_4 FILLER_1_182 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fill_2 FILLER_1_186 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_16 FILLER_1_2 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fill_2 FILLER_1_22 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fill_1 FILLER_1_69 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_4 FILLER_1_72 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fill_2 FILLER_1_76 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_32 FILLER_1_88 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fill_2 FILLER_2_103 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_64 FILLER_2_107 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_4 FILLER_2_171 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_8 FILLER_2_177 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fill_2 FILLER_2_185 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fill_1 FILLER_2_187 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_32 FILLER_2_2 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fill_1 FILLER_2_34 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_16 FILLER_2_37 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_8 FILLER_2_53 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_16 FILLER_2_87 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_8 FILLER_3_128 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_4 FILLER_3_136 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_32 FILLER_3_142 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_8 FILLER_3_174 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_4 FILLER_3_18 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_4 FILLER_3_182 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fill_2 FILLER_3_186 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_16 FILLER_3_2 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fill_2 FILLER_3_22 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fill_2 FILLER_3_58 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fill_1 FILLER_3_60 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fill_1 FILLER_3_72 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_8 FILLER_3_84 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fill_2 FILLER_3_92 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_4 FILLER_4_101 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_16 FILLER_4_107 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fill_1 FILLER_4_123 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_16 FILLER_4_158 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fill_1 FILLER_4_174 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_8 FILLER_4_177 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fill_2 FILLER_4_185 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fill_1 FILLER_4_187 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_32 FILLER_4_2 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fill_1 FILLER_4_34 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_16 FILLER_4_37 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_4 FILLER_4_53 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fill_2 FILLER_4_57 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_8 FILLER_4_93 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_32 FILLER_5_101 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_4 FILLER_5_133 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fill_2 FILLER_5_137 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fill_1 FILLER_5_139 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_32 FILLER_5_142 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_8 FILLER_5_174 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_4 FILLER_5_182 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fill_2 FILLER_5_186 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_64 FILLER_5_2 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_4 FILLER_5_66 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_16 FILLER_5_72 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_8 FILLER_5_88 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fill_1 FILLER_5_96 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fill_2 FILLER_6_102 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fill_1 FILLER_6_104 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_64 FILLER_6_107 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_4 FILLER_6_171 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_8 FILLER_6_177 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fill_2 FILLER_6_185 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fill_1 FILLER_6_187 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_32 FILLER_6_2 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fill_1 FILLER_6_34 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_8 FILLER_6_37 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fill_2 FILLER_6_45 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fill_1 FILLER_6_47 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_16 FILLER_6_82 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_4 FILLER_6_98 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fill_2 FILLER_7_104 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_32 FILLER_7_142 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_8 FILLER_7_174 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_8 FILLER_7_18 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_4 FILLER_7_182 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fill_2 FILLER_7_186 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_16 FILLER_7_2 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_4 FILLER_7_26 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fill_1 FILLER_7_30 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_4 FILLER_7_65 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fill_1 FILLER_7_69 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_32 FILLER_7_72 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fill_2 FILLER_8_103 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_32 FILLER_8_107 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_16 FILLER_8_139 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_8 FILLER_8_155 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_4 FILLER_8_163 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_8 FILLER_8_177 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fill_2 FILLER_8_185 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fill_1 FILLER_8_187 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_32 FILLER_8_2 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fill_1 FILLER_8_34 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_32 FILLER_8_37 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_16 FILLER_9_114 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_8 FILLER_9_130 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fill_2 FILLER_9_138 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_32 FILLER_9_142 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_8 FILLER_9_174 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_8 FILLER_9_18 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_4 FILLER_9_182 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fill_2 FILLER_9_186 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_16 FILLER_9_2 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fill_1 FILLER_9_26 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_8 FILLER_9_61 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fill_1 FILLER_9_69 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fillcap_8 FILLER_9_72 (.VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_0_Left_11 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_0_Right_0 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_10_Left_21 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_10_Right_10 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_1_Left_12 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_1_Right_1 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_2_Left_13 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_2_Right_2 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_3_Left_14 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_3_Right_3 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_4_Left_15 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_4_Right_4 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_5_Left_16 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_5_Right_5 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_6_Left_17 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_6_Right_6 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_7_Left_18 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_7_Right_7 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_8_Left_19 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_8_Right_8 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_9_Left_20 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_9_Right_9 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_0_22 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_0_23 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_0_24 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_0_25 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_0_26 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_10_49 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_10_50 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_10_51 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_10_52 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_10_53 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_1_27 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_1_28 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_2_29 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_2_30 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_2_31 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_3_32 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_3_33 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_4_34 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_4_35 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_4_36 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_5_37 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_5_38 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_6_39 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_6_40 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_6_41 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_7_42 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_7_43 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_8_44 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_8_45 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_8_46 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_9_47 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_9_48 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 _08_ (.I(bp[0]),
    .ZN(_00_),
    .VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__and4_1 _09_ (.A1(bp[9]),
    .A2(bp[8]),
    .A3(bp[1]),
    .A4(bp[0]),
    .Z(_02_),
    .VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__and4_1 _10_ (.A1(bp[5]),
    .A2(bp[4]),
    .A3(bp[7]),
    .A4(bp[6]),
    .Z(_03_),
    .VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__nand4_1 _11_ (.A1(bp[3]),
    .A2(bp[2]),
    .A3(_02_),
    .A4(_03_),
    .ZN(_04_),
    .VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__nor4_1 _12_ (.A1(bp[9]),
    .A2(bp[8]),
    .A3(bp[1]),
    .A4(bp[0]),
    .ZN(_05_),
    .VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__nor4_1 _13_ (.A1(bp[5]),
    .A2(bp[4]),
    .A3(bp[7]),
    .A4(bp[6]),
    .ZN(_06_),
    .VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 _14_ (.A1(_05_),
    .A2(_06_),
    .ZN(_07_),
    .VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__oai31_1 _15_ (.A1(bp[3]),
    .A2(bp[2]),
    .A3(_07_),
    .B(_04_),
    .ZN(_01_),
    .VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__and2_1 _16_ (.A1(en),
    .A2(done),
    .Z(done_o),
    .VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 _17_ (.D(bp[9]),
    .RN(en),
    .CLK(done),
    .Q(code_tc[0]),
    .VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 _18_ (.D(bp[8]),
    .RN(en),
    .CLK(done),
    .Q(code_tc[1]),
    .VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 _19_ (.D(bp[7]),
    .RN(en),
    .CLK(done),
    .Q(code_tc[2]),
    .VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 _20_ (.D(bp[6]),
    .RN(en),
    .CLK(done),
    .Q(code_tc[3]),
    .VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 _21_ (.D(bp[5]),
    .RN(en),
    .CLK(done),
    .Q(code_tc[4]),
    .VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 _22_ (.D(bp[4]),
    .RN(en),
    .CLK(done),
    .Q(code_tc[5]),
    .VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 _23_ (.D(bp[3]),
    .RN(en),
    .CLK(done),
    .Q(code_tc[6]),
    .VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 _24_ (.D(bp[2]),
    .RN(en),
    .CLK(done),
    .Q(code_tc[7]),
    .VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 _25_ (.D(bp[1]),
    .RN(en),
    .CLK(done),
    .Q(code_tc[8]),
    .VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 _26_ (.D(_00_),
    .RN(en),
    .CLK(done),
    .Q(code_tc[9]),
    .VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 _27_ (.D(_01_),
    .RN(en),
    .CLK(done),
    .Q(overload),
    .VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
endmodule
