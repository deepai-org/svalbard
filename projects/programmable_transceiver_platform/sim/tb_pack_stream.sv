`timescale 1ns/1ps
module tb_pack_stream;
 reg clk=0,rst_n=0,mode8=0,sv=0,wr=0;reg[23:0]sample=0;
 wire sr,wv;wire[9:0]word;
 pt_pack dut(clk,rst_n,mode8,sample,sv,sr,word,wv,wr);
 reg queue_bits[0:1023];integer head=0,tail=0,n=0;
 integer m,i,j,width,accepted=0,emitted=0,cycles=0,continuous=0;
 reg output_stalled=0;reg[9:0]saved_word;
 reg stalled=0;reg[31:0]rng=32'h45123487;
 task cycle;
 begin
  clk=0;#3;
  if(!rst_n)begin head=0;tail=0;n=0;stalled=0;output_stalled=0;end
  else begin
   if(output_stalled&&(!wv||word!==saved_word))$fatal(1,"stalled output changed");
   output_stalled=wv&&!wr;saved_word=word;
   if(wv&&wr)begin
    if(n<10)$fatal(1,"output without ten accepted bits");
    for(j=0;j<10;j=j+1)begin
     if(word[j]!==queue_bits[head])$fatal(1,"bit order mode=%0d cycle=%0d bit=%0d",m,cycles,j);
     head=(head+1)%1024;n=n-1;
    end
    emitted=emitted+1;
   end
   if(sv&&sr)begin
    for(j=0;j<width;j=j+1)begin queue_bits[tail]=sample[j];tail=(tail+1)%1024;n=n+1;end
    accepted=accepted+1;continuous=continuous+1;
   end
   if(n>80)$fatal(1,"unbounded accepted backlog %0d",n);
   stalled=sv&&!sr;
  end
  clk=1;#3;cycles=cycles+1;
 end
 endtask
 initial begin
  for(m=0;m<2;m=m+1)begin
   mode8=m;width=m?16:24;rst_n=0;sv=0;cycle();rst_n=1;continuous=0;
   for(i=0;i<20000;i=i+1)begin
    rng=rng^(rng<<13);rng=rng^(rng>>17);rng=rng^(rng<<5);
    if(!stalled)begin sv=(i<10000)||rng[0];sample=rng[23:0];end
    wr=(i<10000)||(i%503>=100&&rng[1]);
    cycle();
    if(i==9999&&continuous<(m?3700:2800))$fatal(1,"throughput regression %0d",continuous);
    // Discard in-flight samples only at explicit reset, including stalled input.
    if(i>=10000&&i%997==0)begin rst_n=0;sv=0;cycle();rst_n=1;end
   end
   sv=0;wr=1;repeat(20)cycle();
   if(n>=10||wv)$fatal(1,"failed to drain complete words");
  end
  $display("PACK_STREAM_PASS cycles=%0d samples=%0d words=%0d",cycles,accepted,emitted);$finish;
 end
endmodule
