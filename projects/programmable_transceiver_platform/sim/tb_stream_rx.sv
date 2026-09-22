`timescale 1ns/1ps
module tb_stream_rx;
 reg clk=0,rst=1,mode=0,wr=1,qr=1;reg[9:0]word=0;
 wire[9:0]data;wire wv,qv,cv,fault;wire[3:0]op;wire[7:0]arg;
 pt_stream_rx dut(clk,rst,mode,word,wr,qr,data,wv,qv,cv,fault,op,arg);
 reg sampled_w,sampled_q;reg[9:0]sampled_data;
 integer fd,rc,m,r,w,a,b,ef,kind,value,cycles=0;
 initial begin
  fd=$fopen("/out/stream-vectors.txt","r");if(!fd)$fatal(1,"missing vectors");
  while(!$feof(fd))begin
   rc=$fscanf(fd,"%h %h %h %h %h %h %h %h\n",m,r,w,a,b,ef,kind,value);
   if(rc!=8)$fatal(1,"malformed vector");
   clk=0;mode=m;rst=!r;word=w;wr=a;qr=b;#4;sampled_w=wv;sampled_q=qv;sampled_data=data;#1;clk=1;#1;
   if(fault!==ef[0]||sampled_w!==(kind==1)||sampled_q!==(kind==2)||cv!==(kind==3))$fatal(1,"event mismatch cycle %d kind %d fault %b/%b",cycles,kind,fault,ef[0]);
   if((sampled_w||sampled_q)&&sampled_data!==value[9:0])$fatal(1,"payload mismatch %d",cycles);
   if(cv&&{op,arg}!==value[11:0])$fatal(1,"command mismatch %d",cycles);
   #4;cycles=cycles+1;
  end
  $display("STREAM_RX_PASS cycles=%0d",cycles);$finish;
 end
endmodule
