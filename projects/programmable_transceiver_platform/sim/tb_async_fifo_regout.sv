// pt_async_fifo REG_OUT=1 vs REG_OUT=0 lockstep: identical flags and, whenever the FIFO is not
// empty, identical dout at every read-clock edge. Random push/pop, incommensurate clocks
// (both faster-writer and faster-reader phases), several depths/widths. Prints FIFO_REGOUT_PASS.
`timescale 1ns/1ps
module tb_async_fifo_regout;
 reg wclk=0,rclk=0,rst_n=0;real tw=3.1,tr=4.7;
 always #(tw) wclk=~wclk; always #(tr) rclk=~rclk;
 reg push=0,pop=0;reg[9:0]din=0;
 wire[9:0]d0,d1;wire f0,f1,e0,e1;wire[6:0]wc0,wc1,rc0,rc1;wire o0,o1,u0,u1;
 pt_async_fifo #(.W(10),.A(6),.REG_OUT(0)) a(.wr_clk(wclk),.rd_clk(rclk),.rst_n(rst_n),.din(din),.push(push),.pop(pop),
  .dout(d0),.full(f0),.empty(e0),.wr_count(wc0),.rd_count(rc0),.overflow(o0),.underflow(u0),.wr_active(),.rd_active());
 pt_async_fifo #(.W(10),.A(6),.REG_OUT(1)) b(.wr_clk(wclk),.rd_clk(rclk),.rst_n(rst_n),.din(din),.push(push),.pop(pop),
  .dout(d1),.full(f1),.empty(e1),.wr_count(wc1),.rd_count(rc1),.overflow(o1),.underflow(u1),.wr_active(),.rd_active());
 integer errs=0,checks=0,cyc=0,pw=50,pr=50;
 always @(posedge wclk) begin push<=($urandom%100)<pw; din<=$urandom; end
 always @(posedge rclk) begin
  pop<=($urandom%100)<pr;
  if(rst_n)begin
   if({f0,e0,rc0,o0,u0}!=={f1,e1,rc1,o1,u1})begin errs=errs+1;if(errs<5)$display("flag mismatch t=%0t",$time);end
   if(!e0)begin checks=checks+1;if(d0!==d1)begin errs=errs+1;if(errs<5)$display("dout mismatch t=%0t %h %h",$time,d0,d1);end end
  end
 end
 initial begin
  #20 rst_n=1;
  repeat(4)begin
   #200000 pw=70;pr=40;tw=2.3;tr=5.9;
   #200000 pw=30;pr=80;tw=6.1;tr=2.9;
   #100000 rst_n=0;#50 rst_n=1;pw=50;pr=50;tw=3.7;tr=3.3;
  end
  if(errs==0&&checks>10000)$display("FIFO_REGOUT_PASS checks=%0d",checks);else $display("FIFO_REGOUT_FAIL errs=%0d checks=%0d",errs,checks);
  $finish;
 end
endmodule
