`timescale 1ns/1ps
module tb_dense_transport;
 reg clk=0,rst_n=1,owner=0;reg[6:0]wc=0;reg[5:0]qc=0;
 reg[9:0]wd=0,qd=0,in_word=0;reg[3:0]op=0;reg[7:0]arg=0;
 reg wr=1,qr=1;
 wire wp,qp,wv,qv,cv,fault;wire[9:0]word,data;wire[3:0]rx_op;wire[7:0]rx_arg;
 pt_dense_tx tx(clk,rst_n,owner,wd,qd,wc,qc,op,arg,wp,qp,word);
 pt_dense_rx rx(clk,rst_n,owner,in_word,wr,qr,data,wv,qv,cv,fault,rx_op,rx_arg);
 integer fd,fo,rc,reset_bit,own,w,q,x,y,o,a,iw,rw,rq,ew,eq,expected,evw,evq,ef,ec,eo,ea,cycles=0;
 initial begin
  fd=$fopen("vectors.txt","r");fo=$fopen("actual.txt","w");
  if(!fd||!fo)$fatal(1,"missing dense vectors/output");
  while(!$feof(fd))begin
   rc=$fscanf(fd,"%h %h %h %h %h %h %h %h %h %h %h\n",reset_bit,own,w,q,x,y,o,a,iw,rw,rq);
   if(rc!=11)$fatal(1,"bad dense vector");
   clk=0;rst_n=!reset_bit;owner=own;wc=w;qc=q;wd=x;qd=y;op=o;arg=a;in_word=iw;wr=rw;qr=rq;#4;
   $fwrite(fo,"%h %h %h %h %h %h %h %h %h\n",word,wp,qp,data,wv,qv,cv,fault,{rx_op,rx_arg});
   #1;clk=1;#5;cycles=cycles+1;
  end
  $fclose(fo);$display("DENSE_TRANSPORT_RUN cycles=%0d",cycles);$finish;
 end
endmodule
