`timescale 1ns/1ps
// Vector bench for the AC-1 sample/quad converters (pt_sample_pack / pt_sample_unpack).
// (File name kept from the paired engine for the make target transceiver-pair-gearbox.)
module tb_pair_gearbox;
 reg clk=0,rst_n=1,mode8=0,pv=0,uv=0,ur=0;
 reg[23:0]pd=0;reg[39:0]ud=0;
 wire po,ui,uo;wire[39:0]pq;wire[23:0]uq;
 pt_sample_pack packer(clk,rst_n,mode8,pd,pv,pq,po,1'b0,);
 pt_sample_unpack unpacker(clk,rst_n,mode8,ud,uv,ui,uq,uo,ur);
 integer fd,fo,rc,r,m,b,e,f;reg[23:0]a;reg[39:0]d;
 initial begin
  fd=$fopen("vectors.txt","r");fo=$fopen("actual.txt","w");
  if(!fd||!fo)$fatal(1,"Missing gearbox vectors/output");
  while(!$feof(fd))begin
   rc=$fscanf(fd,"%h %h %h %h %h %h %h\n",r,m,a,b,d,e,f);
   if(rc!=7)$fatal(1,"Malformed gearbox vector");
   clk=0;rst_n=!r;mode8=m;pd=a;pv=b;ud=d;uv=e;ur=f;#4;
   $fwrite(fo,"%h %h %h %h %h\n",po,pq,ui,uo,uq);
   #1;clk=1;#5;
  end
  $fclose(fo);$finish;
 end
endmodule
