`timescale 1ns/1ps
module tb_dense_pair;
 reg clk=0,rst_n=1,owner=0,wr=1,qr=1;
 reg[6:0]wc=0,qc=0;reg[19:0]wd=0,qd=0,in_pair=0;reg[3:0]op=0;reg[7:0]arg=0;
 wire wp,qp,cv,fault;wire[19:0]tx_pair,data;wire[1:0]wv,qv;wire[3:0]rx_op;wire[7:0]rx_arg;
 pt_dense_pair_tx tx(clk,rst_n,owner,wd,qd,wc,qc,op,arg,wp,qp,tx_pair);
 pt_dense_pair_rx rx(clk,rst_n,owner,in_pair,wr,qr,data,wv,qv,cv,fault,rx_op,rx_arg);
 integer fd,fo,rc,r,o,w,q,x,y,c,a,ip,rw,rq;
 initial begin
  fd=$fopen("vectors.txt","r");fo=$fopen("actual.txt","w");
  if(!fd||!fo)$fatal(1,"Missing pair transport vectors/output");
  while(!$feof(fd))begin
   rc=$fscanf(fd,"%h %h %h %h %h %h %h %h %h %h %h\n",r,o,w,q,x,y,c,a,ip,rw,rq);
   if(rc!=11)$fatal(1,"Malformed pair transport vector");
   clk=0;rst_n=!r;owner=o;wc=w;qc=q;wd=x;qd=y;op=c;arg=a;in_pair=ip;wr=rw;qr=rq;#4;
   $fwrite(fo,"%h %h %h %h %h %h %h %h %h\n",tx_pair,wp,qp,data,wv,qv,cv,fault,{rx_op,rx_arg});
   #1;clk=1;#5;
  end
  $fclose(fo);$finish;
 end
endmodule
