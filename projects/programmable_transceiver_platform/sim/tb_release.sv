`timescale 1ns/1ps
module tb_release;
 reg clk=0,rst=1;always #5 clk=~clk;
 wire[9:0]word,wd,qd;wire wp,qp,wv,qv,fault,locked,cv;wire[3:0]op;wire[7:0]arg;
 pt_frame_tx tx(clk,rst,1'b1,10'h123,10'h256,7'd52,6'd7,wp,qp,word);
 // Refuse precisely the last pipelined output, after memory release has stopped.
 wire ready=rx.release_frame;
 pt_frame_rx rx(clk,rst,1'b1,word,wd,qd,wv,qv,ready,ready,fault,locked,cv,op,arg);
 integer seenw=0,seenq=0;
 always @(posedge clk)begin
  if(wv&&ready)begin if(wd!==10'h123)$fatal(1,"wired pipeline data");seenw=seenw+1;end
  if(qv&&ready)begin if(qd!==10'h256)$fatal(1,"IQ pipeline data");seenq=seenq+1;end
 end
 initial begin
  #1;rst=0;#30;rst=1;
  wait(fault);#1;
  if(seenw!=51||seenq!=7)$fatal(1,"tail fault counts %d %d",seenw,seenq);
  if(wv||qv)$fatal(1,"pending output escaped sticky fault");
  #100;if(!fault)$fatal(1,"fault not sticky");
  $display("RELEASE_PASS last pending word readiness checked");$finish;
 end
 initial begin #10000;$fatal(1,"missing tail fault");end
endmodule
