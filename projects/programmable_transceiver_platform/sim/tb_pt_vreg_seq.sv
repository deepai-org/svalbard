// Self-checking test of rtl/pt_vreg_seq.sv: bypassed rings never held; >= 50 us hold of a regulated
// ring after island power-up and after leaving bypass; independent bypassed ring unaffected; reset
// state passes. Prints VREG_SEQ_PASS.
`timescale 1ns/1ps
module tb_pt_vreg_seq;
 reg rst_n=0,ref_clk=0,on=0,txb=1,rxb=1;
 always #5 ref_clk=~ref_clk;                       // 100 MHz reference (worst case for the 50 us bound)
 wire tx_ok,rx_ok;
 pt_vreg_seq dut(.rst_n(rst_n),.ref_clk(ref_clk),.pll_on(on),.tx_bypass(txb),.rx_bypass(rxb),.tx_ok(tx_ok),.rx_ok(rx_ok));
 integer errs=0;realtime t_on,t_rel;
 task chk(input a,input b,input[8*48-1:0]what);begin
  if(tx_ok!==a||rx_ok!==b)begin errs=errs+1;$display("FAIL %0s: tx_ok=%b rx_ok=%b",what,tx_ok,rx_ok);end
  else $display("ok   %0s",what);end endtask
 // measure the hold duration of rx_ok after a trigger
 task hold_time(output realtime dur);begin
  t_on=$realtime;wait(rx_ok===1'b0);wait(rx_ok===1'b1);dur=$realtime-t_on;end endtask
 realtime d;
 initial begin
  #100 rst_n=1; #100 chk(1,1,"reset: both pass");
  on=1; #1000 chk(1,1,"island on, both bypassed: not held");
  #60000;
  rxb=0; fork hold_time(d); join
  if(d<50000.0)begin errs=errs+1;$display("FAIL rx leave-bypass hold %0.1f ns < 50 us",d);end else $display("ok   rx leave-bypass hold %0.1f ns",d);
  chk(1,1,"after hold");
  on=0; txb=0; #1000; on=1; t_rel=$realtime; #20;
  #100 chk(0,0,"island power-up, both regulated: both held");
  wait(tx_ok===1'b1);
  if($realtime-t_rel<50000.0)begin errs=errs+1;$display("FAIL power-up hold %0.1f ns",$realtime-t_rel);end
  else $display("ok   power-up hold %0.1f ns",$realtime-t_rel);
  txb=1; #200 chk(1,1,"tx back to bypass: passes at once");
  if(errs==0)$display("VREG_SEQ_PASS");else $display("VREG_SEQ_FAIL %0d",errs);
  $finish;
 end
endmodule
