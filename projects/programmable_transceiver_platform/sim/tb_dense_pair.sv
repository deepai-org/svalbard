`timescale 1ns/1ps
// Vector bench for the AC-1 quad frame engines (pt_quad_tx / pt_quad_rx), one row per engine clock.
// (File name kept from the paired engine for the make target transceiver-dense-pair.)
module tb_dense_pair;
 reg clk=0,rst_n=1,owner=0,wr=1,qr=1;
 reg[5:0]wc=0,qc=0;reg[39:0]wd=0,qd=0,in_quad=0;reg[3:0]op=0;reg[7:0]arg=0;
 wire wp,qp,cv,fault;wire[39:0]tx_quad,data;wire[2:0]wv,qv;wire[3:0]rx_op;wire[7:0]rx_arg;
 pt_quad_tx #(.CW(5)) tx(clk,rst_n,owner,wd,qd,wc,qc,op,arg,wp,qp,tx_quad,1'b0,7'd0,1'b0,6'd0,7'd0,);
 pt_quad_rx rx(clk,rst_n,owner,in_quad,wr,qr,data,wv,qv,cv,fault,rx_op,rx_arg);
 integer fd,fo,rc,r,o,w,q,c,a,rw,rq;reg[39:0]x,y,iq;
 initial begin
  fd=$fopen("vectors.txt","r");fo=$fopen("actual.txt","w");
  if(!fd||!fo)$fatal(1,"Missing quad transport vectors/output");
  while(!$feof(fd))begin
   rc=$fscanf(fd,"%h %h %h %h %h %h %h %h %h %h %h\n",r,o,w,q,x,y,c,a,iq,rw,rq);
   if(rc!=11)$fatal(1,"Malformed quad transport vector");
   clk=0;rst_n=!r;owner=o;wc=w;qc=q;wd=x;qd=y;op=c;arg=a;in_quad=iq;wr=rw;qr=rq;#4;
   $fwrite(fo,"%h %h %h %h %h %h %h %h %h\n",tx_quad,wp,qp,data,wv,qv,cv,fault,{rx_op,rx_arg});
   #1;clk=1;#5;
  end
  $fclose(fo);$finish;
 end
endmodule
