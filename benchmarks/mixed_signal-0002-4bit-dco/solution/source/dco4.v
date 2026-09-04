module dco4(input EN, CTRL0, CTRL1, CTRL2, CTRL3, output OUT, inout VDD, VSS);
  wire R0,D0,D1,D2,D3,D4,D5,D6,D7,D8,D9,D10,D11,D12,D13,D14,D15;
  wire L00,L01,L02,L03,L04,L05,L06,L07,L10,L11,L12,L13,L20,L21,FB;
  wire CLKD,Q,QB;

  gf180mcu_fd_sc_mcu7t5v0__nand2_4 XG(.A1(FB),.A2(EN),.ZN(R0));
  gf180mcu_fd_sc_mcu7t5v0__dlyb_4 XD00(.I(R0),.Z(D0));
  gf180mcu_fd_sc_mcu7t5v0__dlyb_4 XD01(.I(D0),.Z(D1));
  gf180mcu_fd_sc_mcu7t5v0__dlyb_4 XD02(.I(D1),.Z(D2));
  gf180mcu_fd_sc_mcu7t5v0__dlyb_4 XD03(.I(D2),.Z(D3));
  gf180mcu_fd_sc_mcu7t5v0__dlyb_4 XD04(.I(D3),.Z(D4));
  gf180mcu_fd_sc_mcu7t5v0__dlyb_4 XD05(.I(D4),.Z(D5));
  gf180mcu_fd_sc_mcu7t5v0__dlyb_4 XD06(.I(D5),.Z(D6));
  gf180mcu_fd_sc_mcu7t5v0__dlyb_4 XD07(.I(D6),.Z(D7));
  gf180mcu_fd_sc_mcu7t5v0__dlyb_4 XD08(.I(D7),.Z(D8));
  gf180mcu_fd_sc_mcu7t5v0__dlyb_4 XD09(.I(D8),.Z(D9));
  gf180mcu_fd_sc_mcu7t5v0__dlyb_4 XD10(.I(D9),.Z(D10));
  gf180mcu_fd_sc_mcu7t5v0__dlyb_4 XD11(.I(D10),.Z(D11));
  gf180mcu_fd_sc_mcu7t5v0__dlyb_4 XD12(.I(D11),.Z(D12));
  gf180mcu_fd_sc_mcu7t5v0__dlyb_4 XD13(.I(D12),.Z(D13));
  gf180mcu_fd_sc_mcu7t5v0__dlyb_4 XD14(.I(D13),.Z(D14));
  gf180mcu_fd_sc_mcu7t5v0__dlyb_4 XD15(.I(D14),.Z(D15));

  gf180mcu_fd_sc_mcu7t5v0__mux2_1 XM00(.I0(D0), .I1(D1), .S(CTRL0),.Z(L00));
  gf180mcu_fd_sc_mcu7t5v0__mux2_1 XM01(.I0(D2), .I1(D3), .S(CTRL0),.Z(L01));
  gf180mcu_fd_sc_mcu7t5v0__mux2_1 XM02(.I0(D4), .I1(D5), .S(CTRL0),.Z(L02));
  gf180mcu_fd_sc_mcu7t5v0__mux2_1 XM03(.I0(D6), .I1(D7), .S(CTRL0),.Z(L03));
  gf180mcu_fd_sc_mcu7t5v0__mux2_1 XM04(.I0(D8), .I1(D9), .S(CTRL0),.Z(L04));
  gf180mcu_fd_sc_mcu7t5v0__mux2_1 XM05(.I0(D10),.I1(D11),.S(CTRL0),.Z(L05));
  gf180mcu_fd_sc_mcu7t5v0__mux2_1 XM06(.I0(D12),.I1(D13),.S(CTRL0),.Z(L06));
  gf180mcu_fd_sc_mcu7t5v0__mux2_1 XM07(.I0(D14),.I1(D15),.S(CTRL0),.Z(L07));
  gf180mcu_fd_sc_mcu7t5v0__mux2_1 XM10(.I0(L00),.I1(L01),.S(CTRL1),.Z(L10));
  gf180mcu_fd_sc_mcu7t5v0__mux2_1 XM11(.I0(L02),.I1(L03),.S(CTRL1),.Z(L11));
  gf180mcu_fd_sc_mcu7t5v0__mux2_1 XM12(.I0(L04),.I1(L05),.S(CTRL1),.Z(L12));
  gf180mcu_fd_sc_mcu7t5v0__mux2_1 XM13(.I0(L06),.I1(L07),.S(CTRL1),.Z(L13));
  gf180mcu_fd_sc_mcu7t5v0__mux2_1 XM20(.I0(L10),.I1(L11),.S(CTRL2),.Z(L20));
  gf180mcu_fd_sc_mcu7t5v0__mux2_1 XM21(.I0(L12),.I1(L13),.S(CTRL2),.Z(L21));
  gf180mcu_fd_sc_mcu7t5v0__mux2_1 XM30(.I0(L20),.I1(L21),.S(CTRL3),.Z(FB));

  gf180mcu_fd_sc_mcu7t5v0__buf_1 XCLK(.I(FB),.Z(CLKD));
  gf180mcu_fd_sc_mcu7t5v0__inv_1 XQI(.I(Q),.ZN(QB));
  gf180mcu_fd_sc_mcu7t5v0__dffrnq_2 XDIV(.D(QB),.RN(EN),.CLK(CLKD),.Q(Q));
  gf180mcu_fd_sc_mcu7t5v0__buf_4 XOB(.I(Q),.Z(OUT));
endmodule
