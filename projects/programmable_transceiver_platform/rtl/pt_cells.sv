// Physical cells that must survive synthesis unchanged (clock dividers'
// output buffers and clock-select muxes). This is the only library-specific
// RTL of the macro: change the cell names here to retarget the library.
// Simulation and formal use the behavioural branch.
`ifdef SYNTHESIS
(* blackbox *) module gf180mcu_fd_sc_mcu7t5v0__mux2_1(input wire I0,I1,S,output wire Z);
endmodule
(* blackbox *) module gf180mcu_fd_sc_mcu7t5v0__mux2_2(input wire I0,I1,S,output wire Z);
endmodule
(* blackbox *) module gf180mcu_fd_sc_mcu7t5v0__clkbuf_8(input wire I,output wire Z);
endmodule
(* blackbox *) module gf180mcu_fd_sc_mcu7t5v0__buf_4(input wire I,output wire Z);
endmodule
(* blackbox *) module gf180mcu_fd_sc_mcu7t5v0__buf_1(input wire I,output wire Z);
endmodule
(* blackbox *) module gf180mcu_fd_sc_mcu7t5v0__dffrnq_4(input wire D,RN,CLK,output wire Q);
endmodule
`endif

// Generated-clock source flop (divider / Johnson output that becomes a clock): a kept x4 flop.
// A clock-source net sits between two clock trees, so neither CTS nor the resizer buffers it; with
// a synthesized dffrnq_1 the hcore divider net had 0.14 pF and a 5.2 ns slew at ss_032C_3v15
// (AC1_R4: hcore insertion delay 13.5 ns, 8-10 ns of hddr<->hcore skew).
module pt_clock_dff(input wire clk,rst_n,d,output wire q);
`ifdef SYNTHESIS
 (* keep=1,dont_touch=1 *) gf180mcu_fd_sc_mcu7t5v0__dffrnq_4 cell(.D(d),.RN(rst_n),.CLK(clk),.Q(q));
`else
 reg r;
 always @(posedge clk or negedge rst_n) if(!rst_n) r<=1'b0; else r<=d;
 assign q=r;
`endif
endmodule

// Clock root buffer at a divider output: keeps the divider's own feedback
// ahead of the generated clock's tree (otherwise CTS can route the divider
// feedback through the whole tree it drives).
// (timing 2026-11-11: clkbuf_8; OpenROAD ignores the Verilog keep / dont_touch attributes for sizing,
// so the divider flop in front may be resized down: it then drives only this buffer.)
module pt_clock_buf(input wire I,output wire Z);
`ifdef SYNTHESIS
 (* keep=1,dont_touch=1 *) gf180mcu_fd_sc_mcu7t5v0__clkbuf_8 cell(.I(I),.Z(Z));
`else
 assign Z=I;
`endif
endmodule

// Stopped-only clock select (S changes only while every destination is held
// in reset), kept as one physical mux so STA can define clocks at its output.
// Drive (timing 2026-11-11): a kept mux2_2 into a kept clkbuf_8 (the generated clock is defined at
// cell/Z). TC4: the mux2_1 alone took 5.2 ns to the CTS root (rf_tx_clk insertion 9.7 ns at ss).
module pt_clock_mux(input wire I0,I1,S,output wire Z);
`ifdef SYNTHESIS
 wire m;
 (* keep=1,dont_touch=1 *) gf180mcu_fd_sc_mcu7t5v0__mux2_2 cell(.I0(I0),.I1(I1),.S(S),.Z(m));
 (* keep=1,dont_touch=1 *) gf180mcu_fd_sc_mcu7t5v0__clkbuf_8 drv(.I(m),.Z(Z));
`else
 assign Z=S?I1:I0;
`endif
endmodule

// HB-1 D2H launch stagger: a fixed two-stage delay (two kept buf_1, no repair may touch them) and
// a kept select mux. Characterized in-window libraries (buf_1 into buf_1): 0.38 ns/stage ss_032C_3v15,
// 0.19 ns/stage ff_022C_3v35, so the staggered group lags by ~0.4-0.8 ns plus wire (not 1/2 UI).
module pt_stagger(input wire I,S,output wire Z);
`ifdef SYNTHESIS
 wire a,b;
 (* keep=1,dont_touch=1 *) gf180mcu_fd_sc_mcu7t5v0__buf_1 d0(.I(I),.Z(a));
 (* keep=1,dont_touch=1 *) gf180mcu_fd_sc_mcu7t5v0__buf_1 d1(.I(a),.Z(b));
 (* keep=1,dont_touch=1 *) gf180mcu_fd_sc_mcu7t5v0__mux2_2 cell(.I0(I),.I1(b),.S(S),.Z(Z));
`else
 assign Z=I;   // zero-delay simulation: the stagger is a physical delay only
`endif
endmodule

// D2H forwarded-clock output select: the same kept mux2_2 as every data lane (pt_stagger), so the
// clock pin and the data pins leave through matched cells (source-synchronous skew; AC1_R4 had a
// synthesized oai21_1 here, ~3.6 ns later than the data lanes at ss_032C_3v15).
module pt_out_mux(input wire I0,I1,S,output wire Z);
`ifdef SYNTHESIS
 (* keep=1,dont_touch=1 *) gf180mcu_fd_sc_mcu7t5v0__mux2_2 cell(.I0(I0),.I1(I1),.S(S),.Z(Z));
`else
 assign Z=S?I1:I0;
`endif
endmodule
