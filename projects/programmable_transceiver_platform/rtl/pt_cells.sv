// Physical cells that must survive synthesis unchanged (clock dividers'
// output buffers and clock-select muxes). This is the only library-specific
// RTL of the macro: change the cell names here to retarget the library.
// Simulation and formal use the behavioural branch.
`ifdef SYNTHESIS
(* blackbox *) module gf180mcu_fd_sc_mcu7t5v0__mux2_1(input wire I0,I1,S,output wire Z);
endmodule
(* blackbox *) module gf180mcu_fd_sc_mcu7t5v0__mux2_2(input wire I0,I1,S,output wire Z);
endmodule
(* blackbox *) module gf180mcu_fd_sc_mcu7t5v0__buf_4(input wire I,output wire Z);
endmodule
(* blackbox *) module gf180mcu_fd_sc_mcu7t5v0__buf_1(input wire I,output wire Z);
endmodule
`endif

// Clock root buffer at a divider output: keeps the divider's own feedback
// ahead of the generated clock's tree (otherwise CTS can route the divider
// feedback through the whole tree it drives).
module pt_clock_buf(input wire I,output wire Z);
`ifdef SYNTHESIS
 (* keep=1,dont_touch=1 *) gf180mcu_fd_sc_mcu7t5v0__buf_4 cell(.I(I),.Z(Z));
`else
 assign Z=I;
`endif
endmodule

// Stopped-only clock select (S changes only while every destination is held
// in reset), kept as one physical mux so STA can define clocks at its output.
module pt_clock_mux(input wire I0,I1,S,output wire Z);
`ifdef SYNTHESIS
 (* keep=1,dont_touch=1 *) gf180mcu_fd_sc_mcu7t5v0__mux2_1 cell(.I0(I0),.I1(I1),.S(S),.Z(Z));
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
