// Reduced-rate transport clock (pt_host_rate_clock, debug.host_link.rate). Checks for every
// setting and every switch order: the output period is 1x/2x/4x the host word clock with 50 %
// duty, every output edge while hold_n=1 belongs to a full-width pulse of the selected rate, and
// a switch is always bracketed by hold_n=0 (destinations in reset) before the select changes.
`timescale 1ns/1ps
module tb_host_rate_clock;
 reg clk=0,rst_n=0;reg[1:0]rate=0;
 wire out_clk,hold_n;
 pt_host_rate_clock dut(.clk(clk),.rst_n(rst_n),.rate(rate),.out_clk(out_clk),.hold_n(hold_n));
 always #1.6 clk=!clk;
 integer errors=0;real last_rise=-1,last_fall=-1,high,period;
 integer expect_div;
 function integer divof(input[1:0]r);divof=r==0?1:r==1?2:4;endfunction
 // Pulse widths observed while hold_n=1 for the whole pulse.
 reg stable=0;integer rises=0;
 always @(posedge out_clk)begin
  if(stable&&hold_n&&last_rise>=0)begin
   period=$realtime-last_rise;
   if(period<3.2*expect_div-0.01||period>3.2*expect_div+0.01)begin
    errors=errors+1;$display("ERROR period %0.2f expected %0.2f",period,3.2*expect_div);end
  end
  last_rise=$realtime;if(stable&&hold_n)rises=rises+1;
 end
 always @(negedge out_clk)if(stable&&hold_n&&last_rise>=0)begin
  high=$realtime-last_rise;
  if(high<1.6*expect_div-0.01||high>1.6*expect_div+0.01)begin
   errors=errors+1;$display("ERROR high %0.2f expected %0.2f",high,1.6*expect_div);end
 end
 // The select may only change while destinations are held in reset.
 // hold_n must already be low on the edge before the select changes.
 // (An asynchronous reset clears the select together with every destination.)
 reg[1:0]cur_q=0;reg hold_q=0,was_reset=0;
 always @(negedge rst_n)was_reset=1;
 always @(posedge clk)begin
  #0.2;if(dut.cur!=cur_q&&hold_q&&!was_reset)begin errors=errors+1;$display("ERROR select changed while released");end
  cur_q=dut.cur;hold_q=hold_n;was_reset=!rst_n;
 end
 task settle(input[1:0]r);integer n;begin
  stable=0;rate=r;expect_div=divof(r);
  n=0;while(hold_n&&n<80)begin @(posedge clk);n=n+1;end   // hold must assert if the rate changed
  n=0;while(!hold_n&&n<160)begin @(posedge clk);n=n+1;end
  if(!hold_n)begin errors=errors+1;$display("ERROR hold never released");end
  repeat(4)@(posedge clk);last_rise=-1;rises=0;stable=1;repeat(40)@(posedge clk);
  if(rises<40/expect_div-1)begin errors=errors+1;$display("ERROR %0d output edges for /%0d",rises,expect_div);end
  if(dut.cur!=(r==3?2:r))begin errors=errors+1;$display("ERROR cur %0d for rate %0d",dut.cur,r);end
 end endtask
 // DIG-08a multicycle premise (SDC HOST_RATE_FSM -setup 4): the FSM flops change only on an edge where ce was 1,
 // and ce is high at most one cycle in four. Negative control at the end: a deposit on gap between ce ticks must be seen.
 integer mc_viol=0,ce_gap=99;reg[9:0]fsm_q;reg ce_q=0;
 wire[9:0]fsm={dut.rate_q,dut.want,dut.ne,dut.gap,dut.cur,dut.hold_n};
 always @(posedge clk)begin
  #0.1;if(rst_n&&!ce_q&&fsm!==fsm_q)begin mc_viol=mc_viol+1;if(mc_viol<4)$display("mc %0t %b %b",$time,fsm_q,fsm);end
  if(dut.ce)begin if(ce_gap<3)begin mc_viol=mc_viol+1;$display("ce gap %0d at %0t",ce_gap,$time);end ce_gap=0;end else ce_gap=ce_gap+1;
  fsm_q=fsm;ce_q=dut.ce;
 end
 integer a,b,v0;
 initial begin
  expect_div=1;repeat(3)@(posedge clk);rst_n=1;
  settle(0);
  for(a=0;a<4;a=a+1)for(b=0;b<4;b=b+1)begin settle(a);settle(b);end
  // Reset while in a reduced mode returns to hold, then re-applies the field.
  settle(2);rst_n=0;#5;if(hold_n)begin errors=errors+1;$display("ERROR hold_n during reset");end
  rst_n=1;settle(2);
  if(mc_viol!=0)begin errors=errors+1;$display("ERROR FSM changed outside ce (%0d)",mc_viol);end
  // negative control: change gap between ce ticks; the monitor must count it
  v0=mc_viol;@(posedge clk);while(dut.ce)@(posedge clk);#0.5;force dut.gap=dut.gap+2'd1;@(posedge clk);#0.5;release dut.gap;
  repeat(2)@(posedge clk);#0.5;
  if(mc_viol==v0)begin errors=errors+1;$display("ERROR negative control: deposit outside ce not detected");end
  else $display("negative control detected (%0d)",mc_viol-v0);
  if(errors==0)$display("HOST_RATE_CLOCK_PASS");else $display("HOST_RATE_CLOCK_FAIL %0d",errors);
  $finish;
 end
endmodule
