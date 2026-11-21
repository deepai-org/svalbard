`timescale 1ns/1ps
// DG9-LC-RX lock-step bench (driven by verification/check_linecode.py): pt_lc_rx (alignment decision one
// clock later) against sim/reference/pt_lc_rx_ref.sv (the RTL before the change). The new outputs
// (dout_valid, dout when valid, aligned, code_error) must equal the reference's delayed by exactly one
// clock, except in the clocks where the enable replica is low (both pipelines are cleared there).
// Stimulus: a K28.5-rich ten-bit stream (both disparities plus a few data codes), random valid gaps,
// a bit slip of 0..9 bits every 700 quads (realignment while aligned), a single flipped bit before each
// slip (false / broken commas, code errors), the enable dropped for 10 clocks every 3000.
// -DNEG compares the reference with itself (must report EQ FAIL: the one-clock check is not vacuous).
module tb_lc_rx_retime_equiv;
 reg clk=0,rst_n=0,en=0,dv=0;reg[39:0]din=0;always #5 clk=~clk;
 wire[39:0]d0,d1;wire v0,v1,a0,a1,e0,e1;
 pt_lc_rx_ref o(.clk(clk),.rst_n(rst_n),.en(en),.din(din),.din_valid(dv),.dout(d0),.dout_valid(v0),.aligned(a0),.code_error(e0));
`ifdef NEG
 pt_lc_rx_ref n(.clk(clk),.rst_n(rst_n),.en(en),.din(din),.din_valid(dv),.dout(d1),.dout_valid(v1),.aligned(a1),.code_error(e1));
`else
 pt_lc_rx     n(.clk(clk),.rst_n(rst_n),.en(en),.din(din),.din_valid(dv),.dout(d1),.dout_valid(v1),.aligned(a1),.code_error(e1));
`endif
 reg[39:0]pd;reg pv,pa,pe,pen=0,prev_a=0;reg[3:0]poff;
 integer cyc=0,err=0,nv=0,nre=0,bits_n=0,slip=0,i;reg[159:0]bs;reg[9:0]cg;
 function [9:0] code(input integer r);
  case(r%6) 0:code=10'b0101111100; 1:code=10'b1010000011; 2:code=10'b1001110100; 3:code=10'b0110001011;
   4:code=10'b1010101010; default:code=10'b0101010101; endcase
 endfunction
 always @(posedge clk)begin
  cyc<=cyc+1;
  if(cyc>2&&n.en_r2&&pen)begin
   if(v1!==pv||a1!==pa||e1!==pe||(pv&&d1!==pd))begin
    err=err+1;if(err<6)$display("MISMATCH t=%0d new v%b a%b e%b d%h ref(t-1) v%b a%b e%b d%h",cyc,v1,a1,e1,d1,pv,pa,pe,pd);
   end
  end
  pen<=n.en_r2;pd<=d0;pv<=v0;pa<=a0;pe<=e0;if(v1)nv=nv+1;
  if(n.off!==poff&&a1&&prev_a)nre=nre+1;poff<=n.off;prev_a<=a1;
 end
 initial begin
  bs=0;#22 rst_n=1;en=1;
  for(i=0;i<60000;i=i+1)begin
   @(negedge clk);
   if(i%3000==2999)begin en=0;dv=0;end else if(i%3000==10)en=1;
   if(i%700==0)slip=$urandom%10;
   dv=($urandom%6)!=0;
   if(dv)begin
    while(bits_n<80)begin cg=code(($urandom%3==0)?($urandom%2):($urandom%6));bs=bs|({150'd0,cg}<<bits_n);bits_n=bits_n+10;end
    din=bs[39:0];
    if(i%700==1)din=din^(40'h1<<($urandom%40));
    if(i%700==2)begin bs=bs>>slip;bits_n=bits_n-slip;end
    bs=bs>>40;bits_n=bits_n-40;
   end
  end
  if(nv<10000||nre<20)begin err=err+1;$display("ERROR coverage: delivered %0d realigns %0d",nv,nre);end
  $display("EQ %s mismatches=%0d delivered=%0d realigns_while_aligned=%0d",err?"FAIL":"PASS",err,nv,nre);$finish;
 end
endmodule
