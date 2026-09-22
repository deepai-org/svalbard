`timescale 1ns/1ps
module tb_core;
 parameter MODE=0,V2=1;
 reg rst=1,en=0,source_on=0,corrupt=0;
 reg hc=0,wr=0,wt=0,rr=0,rt=0;
 localparam real HP=MODE?1.6:2.0;
 localparam real WP=MODE?2.0:4.0;
 localparam real RP=MODE?25.0:12.5;
 always #(HP)hc=~hc;
 always #(WP)wr=~wr;
 initial begin #0.7;forever #(WP)wt=~wt;end
 always #(RP)rr=~rr;
 initial begin #1.1;forever #(RP)rt=~rt;end
 reg[9:0]wd=0;reg[23:0]rf=0;
 wire[9:0]out,wiretx;wire[23:0]rftx;wire wvalid,rvalid,wi,rm;wire[15:0]status;
 wire inject;
 generate if(V2)begin
  assign inject=corrupt&&dut.stream_v2.frame_tx.running&&dut.stream_v2.frame_tx.payload.pos==2;
 end else begin
  assign inject=corrupt&&dut.stream_v1.frame_tx.pos==10;
 end endgenerate
 wire[9:0]incoming=out ^ (inject?10'b1:10'b0);
 pt_core #(.STREAM_V2(V2)) dut(rst,en,MODE!=0,hc,hc,wr,wt,rr,rt,incoming,out,wd,source_on,wiretx,wvalid,1'b1,
 rf,source_on,rftx,rvalid,1'b1,status,wi,rm);
 reg[9:0]expectedw[0:32767];reg[23:0]expectedr[0:32767];
 integer producedw=0,producedr=0,seenw=0,seenr=0;integer k,trace;
 initial trace=$fopen(V2?(MODE?"/out/core_v2_1_words.txt":"/out/core_v2_0_words.txt"):MODE?"/out/core1_words.txt":"/out/core0_words.txt","w");
 always @(posedge hc)if(dut.trst&&!corrupt&&source_on!==1'bx)$fdisplay(trace,"%03h",out);
 always @(posedge wr)if(source_on)begin
  expectedw[producedw]=wd;producedw=producedw+1;wd<=(wd+10'd37)^10'h015;
 end
 always @(posedge rr)if(source_on)begin
  expectedr[producedr]=MODE?{rf[23:16],4'b0,rf[11:4],4'b0}:rf;
  producedr=producedr+1;rf<={12'((producedr*13+1024)%4096),12'((producedr*7)%4096)};
 end
 always @(posedge wt)if(wvalid)begin
  if(seenw>=producedw||wiretx!==expectedw[seenw])$fatal(1,"wired order/data mismatch mode=%0d n=%0d got=%h expected=%h",MODE,seenw,wiretx,expectedw[seenw]);
  seenw=seenw+1;
 end
 always @(posedge rt)if(rvalid)begin
  if(seenr>=producedr||rftx!==expectedr[seenr])$fatal(1,"RF order/data mismatch mode=%0d n=%0d got=%h expected=%h",MODE,seenr,rftx,expectedr[seenr]);
  seenr=seenr+1;
 end
 initial begin
  #1;rst=0;#100;rst=1;#15;en=1;#100;source_on=1;
  #60000;
  $display("DEBUG mode=%0d status=%h wravail=%0d iqavail=%0d outw=%0d outr=%0d",MODE,status,dut.wr_avail,dut.iq_avail,dut.wire_out_count,dut.rf_out_count);
  if(seenw<1000||seenr<500)$fatal(1,"insufficient throughput w=%0d iq=%0d",seenw,seenr);
  if((status&16'h1dfe)!=0)$fatal(1,"unexpected fault status=%h",status);
  corrupt=1;#1000;
  if(!status[8])$fatal(1,"protected transport corruption not latched");
  /* Keep injection asserted while checking sticky fault. */ #1000;if(!status[8])$fatal(1,"fault cleared without retrain");
  en=0;source_on=0;#1000;if(status[8])$fatal(1,"disarm failed to clear fault");
  $display("CORE_PASS v2=%0d mode=%0d wired=%0d iq=%0d",V2,MODE,seenw,seenr);$finish;
 end
 always @(posedge hc) if(en && $time>100) begin
  if ((^dut.rf_out.rb)===1'bx || (^dut.unpacker.count)===1'bx || (^dut.iq_receive.count)===1'bx)
    $fatal(1,"X t=%0t rfrb=%h unpackcount=%h iqcount=%h unpackvalid=%b mode=%b",$time,dut.rf_out.rb,dut.unpacker.count,dut.iq_receive.count,dut.unpacked_valid,dut.mode8);
 end
 initial begin #100000;$fatal(1,"timeout");end
endmodule
