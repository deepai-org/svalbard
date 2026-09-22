`timescale 1ns/1ps
module tb_stream_tx;
 reg clk=0,rst=1,mode=0;reg[6:0]wc=0;reg[5:0]qc=0;reg[9:0]wd=0,qd=0;reg[3:0]op=0;reg[7:0]arg=0;
 wire wp,qp;wire[9:0]word;
 pt_stream_tx dut(clk,rst,mode,wd,qd,wc,qc,op,arg,wp,qp,word);
 integer fd,rc,m,r,w,q,x,y,o,a,ew,eq,expected,cycles=0;
 initial begin
  fd=$fopen("/out/stream-tx-vectors.txt","r");if(!fd)$fatal(1,"missing TX vectors");
  while(!$feof(fd))begin
   rc=$fscanf(fd,"%h %h %h %h %h %h %h %h %h %h %h\n",m,r,w,q,x,y,o,a,ew,eq,expected);
   if(rc!=11)$fatal(1,"bad TX vector");
   clk=0;rst=!r;mode=m;wc=w;qc=q;wd=x;qd=y;op=o;arg=a;#4;
   if(!r)begin
    if(word!==expected[9:0]||wp!==ew[0]||qp!==eq[0])$fatal(1,"TX cycle=%0d word=%h expected=%h pops=%b%b/%b%b",cycles,word,expected[9:0],wp,qp,ew[0],eq[0]);
    cycles=cycles+1;
   end
   #1;clk=1;#5;
  end
  $display("STREAM_TX_PASS cycles=%0d",cycles);$finish;
 end
endmodule
