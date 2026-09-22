`timescale 1ns/1ps
module tb_stream_link;
 parameter MODE=0;
 reg clk=0,rx_rst=1,tx_rst=1,noise=1,corrupt=0;
 always #5 clk=~clk;
 wire[9:0]word,data;wire wp,qp,wv,qv,cv,fault,locked;wire[3:0]op;wire[7:0]arg;
 wire[9:0]incoming=noise?10'h3a5:word^((corrupt&&tx.running&&tx.payload.pos==2)?10'b1:10'b0);
 pt_stream_link_tx tx(clk,tx_rst,MODE!=0,10'h3a5,10'h05a,7'd63,6'd63,4'd0,8'd0,wp,qp,word);
 pt_stream_link_rx rx(clk,rx_rst,MODE!=0,incoming,1'b1,1'b1,data,wv,qv,cv,fault,locked,op,arg);
 integer nw=0,nq=0;
 always @(posedge clk)begin
  if(wv)begin if(!locked||data!==10'h3a5)$fatal(1,"wire transfer");nw=nw+1;end
  if(qv)begin if(!locked||data!==10'h05a)$fatal(1,"IQ transfer");nq=nq+1;end
  if(!locked&&(wv||qv||cv))$fatal(1,"effect before training");
 end
 initial begin
  #1;rx_rst=0;tx_rst=0;#100;
  @(negedge clk);rx_rst=1;#200;
  @(negedge clk);tx_rst=1;noise=0;
  #5000;if(!locked||fault||nw<100||nq<20)$fatal(1,"startup/data failure %d %d",nw,nq);
  corrupt=1;wait(fault);#100;if(wv||qv||cv)$fatal(1,"effect after fault");
  // Preamble-like data cannot restart a faulted receiver.
  noise=1;#100;if(!fault)$fatal(1,"automatic reacquisition");
  @(negedge clk);rx_rst=0;tx_rst=0;#100;
  @(negedge clk);rx_rst=1;
  #10300;if(!fault||locked)$fatal(1,"missing acquisition timeout");
  @(negedge clk);rx_rst=0;#100;
  @(negedge clk);rx_rst=1;tx_rst=1;noise=0;corrupt=0;
  #3000;if(fault||!locked)$fatal(1,"explicit restart failure");
  $display("STREAM_LINK_PASS mode=%0d",MODE);$finish;
 end
 initial begin #30000;$fatal(1,"timeout");end
endmodule
