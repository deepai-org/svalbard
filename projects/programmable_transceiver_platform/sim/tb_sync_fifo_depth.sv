`timescale 1ns/1ps
module tb_sync_fifo_depth;
 reg clk=0,rst_n=1,push=0,pop=0;reg[19:0]din=0;
 wire[19:0]d6,d12;wire f6,e6,o6,u6,f12,e12,o12,u12;wire[4:0]c6,c12;
 pt_sync_fifo #(.W(20),.A(4),.DEPTH(6),.LOOKAHEAD(1)) a(clk,rst_n,push,pop,din,d6,f6,e6,c6,o6,u6);
 pt_sync_fifo #(.W(20),.A(4),.DEPTH(12)) b(clk,rst_n,push,pop,din,d12,f12,e12,c12,o12,u12);
 wire[19:0]d7;wire f7,e7,o7,u7;wire[3:0]c7;
 pt_sync_fifo #(.W(20),.A(3),.DEPTH(7)) c(clk,rst_n,push,pop,din,d7,f7,e7,c7,o7,u7);
 integer fd,fo,rc,r,p,q,d;
 initial begin
  fd=$fopen("vectors.txt","r");fo=$fopen("actual.txt","w");
  if(!fd||!fo)$fatal(1,"Missing FIFO depth vectors");
  while(!$feof(fd))begin
   rc=$fscanf(fd,"%h %h %h %h\n",r,p,q,d);
   if(rc!=4)$fatal(1,"Malformed FIFO vector");
   clk=0;rst_n=!r;push=p;pop=q;din=d;#4;
   $fwrite(fo,"%h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h\n",f6,e6,c6,o6,u6,d6,f12,e12,c12,o12,u12,d12,f7,e7,c7,o7,u7,d7);
   #1;clk=1;#5;
  end
  $fclose(fo);$finish;
 end
endmodule
