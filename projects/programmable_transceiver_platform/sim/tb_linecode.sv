`timescale 1ns/1ps
// IX-2 8b/10b offload bench (driven by verification/check_linecode.py):
//  TX: tx_in.hex packed 9-bit symbols (40-bit quads, FWFT source with pop) -> pt_lc_tx with random
//      take stalls -> tx_out.hex (encoded quads in take order).
//  RX: rx_in.hex 40-bit quads of a bit-slipped encoded stream with random valid gaps -> pt_lc_rx
//      -> rx_out.hex (decoded 40-bit output quads), rx_status.txt (aligned, code_error).
module tb_linecode;
 reg clk=0,rst_n=0;always #5 clk=~clk;
 reg[39:0]tx_in[0:4095];reg[39:0]rx_in[0:4095];integer ntx,nrx,ti=0,ri=0,fo,fr,cycles=0,seed=7;
 wire pop,qv,aligned,cerr,dv;wire[39:0]q,dout;reg take=0,din_valid=0;reg[39:0]din=0;
 pt_lc_tx tx(.clk(clk),.rst_n(rst_n),.en(1'b1),.head(tx_in[ti]),.head_valid(ti<ntx),.pop(pop),.q(q),.q_valid(qv),.take(take));
 pt_lc_rx rx(.clk(clk),.rst_n(rst_n),.en(1'b1),.din(din),.din_valid(din_valid),.dout(dout),.dout_valid(dv),.aligned(aligned),.code_error(cerr));
 initial begin
  if(!$value$plusargs("NTX=%d",ntx))ntx=0;if(!$value$plusargs("NRX=%d",nrx))nrx=0;
  $readmemh("tx_in.hex",tx_in);$readmemh("rx_in.hex",rx_in);
  fo=$fopen("tx_out.hex","w");fr=$fopen("rx_out.hex","w");
  #22 rst_n=1;
 end
 always @(posedge clk)if(rst_n)begin
  cycles<=cycles+1;
  if(pop)ti<=ti+1;
  if(take&&qv)$fdisplay(fo,"%h",q);
  if(dv)$fdisplay(fr,"%h",dout);
  if(din_valid)ri<=ri+1;
 end
 always @(negedge clk)if(rst_n)begin
  take<=($random(seed)%5)!=0;
  din_valid<=(ri<nrx)&&(($random(seed)%7)!=0);
  din<=rx_in[ri];
  if(cycles>3*(ntx+nrx)+200)begin $fdisplay(fr,"S %0d %0d",aligned,cerr);$fclose(fo);$fclose(fr);$display("LC_BENCH_DONE");$finish;end
 end
endmodule
