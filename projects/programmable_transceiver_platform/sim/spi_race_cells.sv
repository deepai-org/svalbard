// Delay models of the yosys generic gates/flops for sim/tb_spi_csn_race.sv (gate-level mode).
// Every instance draws its own transport delays from tb_spi_csn_race.seed (so decode glitches and
// asynchronous-reset transients of a mapped netlist are exercised), and a flop whose D changes
// inside its setup/hold window resolves to a RANDOM value (metastability model; counted in
// tb_spi_csn_race.meta_events). Not a timing model of GF180: delays are deliberately spread.
`timescale 1ps/1ps
`define RACE_GATE(NAME,PORTS,EXPR) \
module NAME PORTS; integer d; reg y_r; initial d=80; initial #1 d=80+({$random(tb_spi_csn_race.seed)}%320); \
 wire f=EXPR; always @(f) y_r<= #(d) f; assign Y=y_r; endmodule
`RACE_GATE(\$_NOT_ ,(input A,output Y),~A)
`RACE_GATE(\$_BUF_ ,(input A,output Y),A)
`RACE_GATE(\$_AND_ ,(input A,B,output Y),A&B)
`RACE_GATE(\$_NAND_ ,(input A,B,output Y),~(A&B))
`RACE_GATE(\$_OR_ ,(input A,B,output Y),A|B)
`RACE_GATE(\$_NOR_ ,(input A,B,output Y),~(A|B))
`RACE_GATE(\$_XOR_ ,(input A,B,output Y),A^B)
`RACE_GATE(\$_XNOR_ ,(input A,B,output Y),~(A^B))
`RACE_GATE(\$_ANDNOT_ ,(input A,B,output Y),A&~B)
`RACE_GATE(\$_ORNOT_ ,(input A,B,output Y),A|~B)
`RACE_GATE(\$_MUX_ ,(input A,B,S,output Y),S?B:A)

// D flop, asynchronous active-low reset to 0. EDGE = 1 rising clock, 0 falling clock.
module race_dff #(parameter EDGE=1)(input D,C,R,output Q);
 localparam TW=120; // setup = hold window, ps
 integer dq,dr; reg qc,Rd; time tD,tC; reg v;
 initial begin dq=300;dr=300;qc=1'bx;Rd=1'b1;tD=0;tC=0; #1 dq=300+({$random(tb_spi_csn_race.seed)}%600);
  dr=300+({$random(tb_spi_csn_race.seed)}%600);end
 wire ck=EDGE?C:~C;
 always @(R) Rd<= #(dr) R;
 // stored value: cleared after any capture still in flight when the reset arrived
 always @(negedge R) qc<= #(dq+1) 1'b0;
 always @(posedge ck) if(R!==1'b0)begin
  tC=$time;
  if($time-tD<TW&&$time>TW)begin v=$random(tb_spi_csn_race.seed);tb_spi_csn_race.meta_events=tb_spi_csn_race.meta_events+1;qc<= #(dq+200) v;end
  else qc<= #(dq) D;
 end
 always @(D)begin
  tD=$time;
  if($time-tC<TW&&$time>TW&&R!==1'b0)begin v=$random(tb_spi_csn_race.seed);tb_spi_csn_race.meta_events=tb_spi_csn_race.meta_events+1;qc<= #(dq+200) v;end
 end
 assign Q=(Rd===1'b0)?1'b0:qc;
endmodule
module \$_DFF_PN0_ (input D,C,R,output Q); race_dff #(1) f(D,C,R,Q); endmodule
module \$_DFF_NN0_ (input D,C,R,output Q); race_dff #(0) f(D,C,R,Q); endmodule
