`timescale 1ns/1ps
module tb_sync_fifo_flags;
 reg clk=0,rst_n=0,push=0,pop=0;reg[9:0]din=0;
 wire[9:0]dout;wire full,empty,overflow,underflow;wire[5:0]count;
 pt_sync_fifo dut(clk,rst_n,push,pop,din,dout,full,empty,count,overflow,underflow);
 reg[9:0]queue[0:31];integer head=0,tail=0,n=0,cycles=0;
 reg ov=0,un=0,put,take;integer level,op,i;
 reg[31:0]rng=32'h98654023;
 task check_state;
 begin
  if(full!==(n==32)||empty!==(n==0)||count!==n||overflow!==ov||underflow!==un)
   $fatal(1,"FIFO state cycle=%0d count=%0d expected=%0d",cycles,count,n);
  if(n!=0&&dout!==queue[head])$fatal(1,"FIFO ordering cycle=%0d",cycles);
 end
 endtask
 task cycle;
 begin
  clk=0;#3;
  if(!rst_n)begin n=0;head=0;tail=0;ov=0;un=0;end
  else begin
   check_state();put=push&&(n<32);take=pop&&(n>0);
   if(push&&n==32)ov=1;if(pop&&n==0)un=1;
   if(take)head=(head+1)%32;
   if(put)begin queue[tail]=din;tail=(tail+1)%32;end
   n=n+put-take;
  end
  clk=1;#3;check_state();cycles=cycles+1;
 end
 endtask
 initial begin
  // All occupancies and all four push/pop combinations, including both boundaries.
  for(level=0;level<=32;level=level+1)for(op=0;op<4;op=op+1)begin
   rst_n=0;cycle();rst_n=1;push=1;pop=0;
   for(i=0;i<level;i=i+1)begin din=i+level;cycle();end
   push=op[1];pop=op[0];din=10'h3ab;cycle();
   push=0;pop=1;repeat(34)cycle();
  end
  for(i=0;i<20000;i=i+1)begin
   rng=rng^(rng<<13);rng=rng^(rng>>17);rng=rng^(rng<<5);
   rst_n=i%997!=0;push=rng[0];pop=rng[1];din=rng[11:2];cycle();
  end
  $display("SYNC_FIFO_FLAGS_PASS cycles=%0d boundary_cases=132",cycles);$finish;
 end
endmodule
