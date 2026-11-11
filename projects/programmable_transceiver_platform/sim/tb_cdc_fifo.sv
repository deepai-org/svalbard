`timescale 1ns/1ps
// Randomized check of pt_cdc_fifo (AC-1 transport CDC FIFO) for power-of-two and even
// non-power-of-two depths, with unrelated write/read clocks:
//  * order and integrity of every word (reference queue), no loss, no duplication;
//  * rd_count never exceeds the true occupancy (seen at the read edge) and empty agrees;
//  * a producer that pushes only while ready (one-clock registered, as the transport
//    collector) never overflows; a producer that ignores ready overflows and is flagged;
//  * reads never underflow when gated by !empty.
// Prints CDC_FIFO_PASS.
module tb_cdc_fifo_one #(parameter A=5,DEPTH=24,real WH=4.1,real RH=6.3,integer SEED=1)(output reg done,output integer errors);
 reg wclk=0,rclk=0,rst_n=0,push=0,pop_en=0;reg[39:0]din=0;
 wire[39:0]dout;wire full,empty,ready,ov,un;wire[A:0]rd_count;
 pt_cdc_fifo #(.W(40),.A(A),.DEPTH(DEPTH)) dut(.wr_clk(wclk),.rd_clk(rclk),.rst_n(rst_n),.din(din),.push(push),
  .pop(pop_en&&!empty),.dout(dout),.full(full),.empty(empty),.ready(ready),.rd_count(rd_count),
  .overflow(ov),.underflow(un),.wr_active(),.rd_active(),.wr_ptr(),.rd_ptr(),
  .peek_idx('0),.peek(),.play(1'b0),.play_loop(1'b0),.play_last('0),.spi_clk(1'b0),.spi_we(1'b0),.spi_idx('0),.spi_d(40'd0));
 always #(WH) wclk=~wclk;
 always #(RH) rclk=~rclk;
 integer seed=SEED,wrote=0,read=0,maxocc=0,cycles=0;
 reg[39:0]q[0:65535];
 // registered producer (as the transport collector): accepts while ready, its push register
 // writes the FIFO one clock later
 always @(posedge wclk)if(rst_n)begin
  if(push)begin q[wrote%65536]=din;wrote=wrote+1;end
  push<=ready&&($random(seed)%4!=0);
  din<={$random(seed),8'(wrote+1)};
 end
 always @(posedge rclk)if(rst_n)begin
  cycles=cycles+1;
  if(rd_count>wrote-read)begin errors=errors+1;$display("rd_count %0d > occupancy %0d",rd_count,wrote-read);end
  if(rd_count!=0&&empty)begin errors=errors+1;$display("rd_count %0d while empty",rd_count);end
  if(pop_en&&!empty)begin
   if(dout!==q[read%65536])begin errors=errors+1;if(errors<5)$display("data %h expected %h at %0d",dout,q[read%65536],read);end
   read=read+1;
  end
  if(wrote-read>maxocc)maxocc=wrote-read;
  pop_en<=($random(seed)%3!=0);
 end
 initial begin
  errors=0;done=0;
  #20 rst_n=1;
  #60000;
  if(ov||un)begin errors=errors+1;$display("ov=%b un=%b",ov,un);end
  if(read<1000)begin errors=errors+1;$display("too few reads %0d",read);end
  if(maxocc>DEPTH)begin errors=errors+1;$display("occupancy %0d > depth",maxocc);end
  $display("depth=%0d wrote=%0d read=%0d max_occupancy=%0d errors=%0d",DEPTH,wrote,read,maxocc,errors);
  done=1;
 end
endmodule
module tb_cdc_fifo;
 wire d0,d1,d2,d3,d4;integer e0,e1,e2,e3,e4;
 tb_cdc_fifo_one #(.A(5),.DEPTH(24),.WH(4.1),.RH(6.3),.SEED(3)) f24(d0,e0);
 tb_cdc_fifo_one #(.A(5),.DEPTH(32),.WH(8.0),.RH(6.4),.SEED(5)) f32(d1,e1);
 tb_cdc_fifo_one #(.A(4),.DEPTH(16),.WH(6.4),.RH(8.0),.SEED(7)) f16(d2,e2);
 tb_cdc_fifo_one #(.A(4),.DEPTH(12),.WH(3.3),.RH(9.7),.SEED(9)) f12(d3,e3);
 tb_cdc_fifo_one #(.A(3),.DEPTH(6),.WH(5.0),.RH(5.1),.SEED(11)) f6(d4,e4);
 // overflow detection: a producer that ignores ready on a slow reader must be flagged
 reg wc=0,rc=0,rst=0;wire[39:0]o;wire fu,em,rdy,ovf,unf;wire[5:0]cnt;
 pt_cdc_fifo #(.W(40),.A(5),.DEPTH(24)) flood(.wr_clk(wc),.rd_clk(rc),.rst_n(rst),.din(40'd1),.push(1'b1),.pop(1'b0),
  .dout(o),.full(fu),.empty(em),.ready(rdy),.rd_count(cnt),.overflow(ovf),.underflow(unf),.wr_active(),.rd_active(),.wr_ptr(),.rd_ptr(),
  .peek_idx('0),.peek(),.play(1'b0),.play_loop(1'b0),.play_last('0),.spi_clk(1'b0),.spi_we(1'b0),.spi_idx('0),.spi_d(40'd0));
 always #3 wc=~wc;always #7 rc=~rc;
 initial begin
  #20 rst=1;
  wait(d0&&d1&&d2&&d3&&d4);
  if(!ovf||rdy)begin $display("flood: overflow=%b ready=%b",ovf,rdy);$fatal(1,"CDC_FIFO_FAIL");end
  if(e0+e1+e2+e3+e4)$fatal(1,"CDC_FIFO_FAIL");
  $display("CDC_FIFO_PASS");$finish;
 end
endmodule
