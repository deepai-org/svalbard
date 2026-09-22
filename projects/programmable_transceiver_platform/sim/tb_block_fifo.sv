`timescale 1ns/1ps
module tb_block_fifo;
 reg wr_clk=0,rd_clk=0,rst_n=0;
 always #5 wr_clk=~wr_clk;
 initial begin #2;forever #7 rd_clk=~rd_clk;end
 reg [79:0] wr_data=0;reg[3:0]wr_words=0;
 reg wr_valid=0,rd_ready=0;
 wire wr_ready,rd_valid,wr_fault;wire[79:0]rd_data;wire[3:0]rd_words;
 pt_block_fifo dut(.*);
 reg[83:0]expected[0:100000];integer put=0,take=0;
 integer accepted=0,received=0,bad=0,full_cycles=0,empty_cycles=0;
 integer counts[0:15];integer phase=0,cycles=0,i;
 reg fault_expected=0;reg[3:0]old_wg,old_rg,delta;
 function automatic bit onehot0(input[3:0]x);onehot0=(x==0)||((x&(x-1))==0);endfunction
 always @(negedge wr_clk)begin
  cycles=cycles+1;
  wr_valid=rst_n && (phase==0 || ($urandom_range(0,3)!=0));
  wr_words=$urandom_range(0,15);
  wr_data={$urandom,$urandom,$urandom};
 end
 always @(negedge rd_clk)rd_ready=rst_n && phase!=0 && (phase==2 || $urandom_range(0,3)!=0);
 always @(posedge wr_clk)begin
  old_wg=dut.storage.wg;
  if(rst_n)begin
   if(!wr_ready)full_cycles=full_cycles+1;
   if(wr_valid&&wr_ready)begin
    if(wr_words>=1&&wr_words<=8)begin
     expected[put]={wr_words,wr_data};put=put+1;accepted=accepted+1;counts[wr_words]=counts[wr_words]+1;
    end else begin bad=bad+1;fault_expected=1;end
   end
  end
  #0.001;
  if(rst_n)begin
   delta=old_wg^dut.storage.wg;
   if(!onehot0(delta))$fatal(1,"write Gray jumped");
   if(wr_fault!==fault_expected)$fatal(1,"fault mismatch");
   if(dut.storage.overflow)$fatal(1,"overflow");
  end
 end
 always @(posedge rd_clk)begin
  old_rg=dut.storage.rg;
  if(rst_n)begin
   if(!rd_valid)empty_cycles=empty_cycles+1;
   if(rd_valid&&rd_ready)begin
    if(take>=put)$fatal(1,"unexpected block");
    if({rd_words,rd_data}!==expected[take])$fatal(1,"block mismatch %0d",take);
    take=take+1;received=received+1;
   end
  end
  #0.001;
  if(rst_n)begin
   delta=old_rg^dut.storage.rg;
   if(!onehot0(delta))$fatal(1,"read Gray jumped");
   if(dut.storage.underflow)$fatal(1,"underflow");
  end
 end
 task reset;
  begin
   rst_n=0;wr_valid=0;rd_ready=0;put=0;take=0;fault_expected=0;
   #31;
   if(wr_ready!==0||rd_valid!==0||wr_fault!==0)$fatal(1,"reset outputs");
   // Deliberately delay the storage synchronizer's release in each domain.
   // This is a digital release-skew test, not a metastability simulation.
   force dut.storage.wr_reset=0;force dut.storage.rd_reset=0;
   rst_n=1;
   #43;
   if(wr_ready!==0||rd_valid!==0)$fatal(1,"premature handshake");
   release dut.storage.wr_reset;
   #29;
   if(rd_valid!==0)$fatal(1,"premature read release");
   release dut.storage.rd_reset;
  end
 endtask
 initial begin
  for(i=0;i<16;i=i+1)counts[i]=0;
  #1;reset();#1000;phase=1;#100000;
  reset();#100000;
  // Stop producer, drain all accepted blocks.
  @(negedge wr_clk);force wr_valid=0;phase=2;#1000;
  if(take!=put)$fatal(1,"drain incomplete");
  if(accepted<1000||received<1000||bad<100||full_cycles<50||empty_cycles<50)$fatal(1,"coverage");
  for(i=1;i<=8;i=i+1)if(counts[i]<100)$fatal(1,"count coverage");
  $display("PASS block FIFO accepted=%0d received=%0d invalid=%0d blocked=%0d empty=%0d",accepted,received,bad,full_cycles,empty_cycles);
  $finish;
 end
endmodule
