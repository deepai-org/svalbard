// Candidate CDC FIFO. Gray pointers; dual-clock storage needs physical implementation.
module pt_async_fifo #(parameter W=10, A=6)(
 input wire wr_clk, rd_clk, rst_n, input wire [W-1:0] din,
 input wire push, pop, output wire [W-1:0] dout,
 output wire full, empty, output wire [A:0] wr_count, rd_count,
 output reg overflow, underflow);
 (* async_reg="true" *) reg[1:0]wr_reset,rd_reset;
 always @(posedge wr_clk or negedge rst_n)
  if(!rst_n)wr_reset<=0;else wr_reset<={wr_reset[0],1'b1};
 always @(posedge rd_clk or negedge rst_n)
  if(!rst_n)rd_reset<=0;else rd_reset<={rd_reset[0],1'b1};
 wire wr_ready=wr_reset[1],rd_ready=rd_reset[1];
 reg [W-1:0] mem[0:(1<<A)-1];
 reg [A:0] wb,rb,wg,rg,rg1,rg2,wg1,wg2;
 wire [A:0] wn=wb+1'b1;
 function automatic [A:0] binary(input [A:0] g);
 // Parallel prefix XOR; no added count latency or CDC stage.
 integer stride; begin binary=g; for(stride=1;stride<=A;stride=stride*2) binary=binary^(binary>>stride); end endfunction
 assign full=(wg=={~rg2[A:A-1],rg2[A-2:0]});
 assign empty=(rg==wg2); assign wr_count=wb-binary(rg2);
 assign rd_count=binary(wg2)-rb;
 assign dout=mem[rb[A-1:0]];
 always @(posedge wr_clk or negedge wr_ready) begin
  if(!wr_ready) begin wb<=0;wg<=0;rg1<=0;rg2<=0;overflow<=0;end
  else begin rg1<=rg;rg2<=rg1;
   if(push) if(!full) begin mem[wb[A-1:0]]<=din;wb<=wn;wg<=(wn>>1)^wn;end else overflow<=1;
  end
 end
 always @(posedge rd_clk or negedge rd_ready) begin
  if(!rd_ready) begin rb<=0;rg<=0;wg1<=0;wg2<=0;underflow<=0;end
  else begin wg1<=wg;wg2<=wg1;
   if(pop) if(!empty) begin rb<=rb+1'b1;rg<=((rb+1'b1)>>1)^(rb+1'b1);end else underflow<=1;
  end
 end
endmodule

module pt_sync_fifo #(parameter W=10,A=5)(input wire clk,rst_n,
 input wire push,pop,input wire[W-1:0]din,output wire[W-1:0]dout,
 output reg full,empty,output reg[A:0]count,output reg overflow,underflow);
 reg[W-1:0]mem[0:(1<<A)-1];reg[A-1:0]wp,rp;
 assign dout=mem[rp];
 wire put=push&&!full,take=pop&&!empty;
 always @(posedge clk or negedge rst_n) begin
  if(!rst_n)begin full<=0;empty<=1;wp<=0;rp<=0;count<=0;overflow<=0;underflow<=0;end
  else begin
   if(put)begin mem[wp]<=din;wp<=wp+1'b1;end
   if(take)rp<=rp+1'b1;
   case({put,take})
    2'b10:begin count<=count+1'b1;full<=count==((1<<A)-1);empty<=0;end
    2'b01:begin count<=count-1'b1;full<=0;empty<=count==1;end
    default:begin end
   endcase
   if(push&&full)overflow<=1;if(pop&&empty)underflow<=1;
  end
 end
endmodule

module pt_sync_bit(input wire clk,rst_n,d,output reg q);
 (* async_reg="true" *) reg meta;
 always @(posedge clk or negedge rst_n)if(!rst_n)begin meta<=0;q<=0;end else begin meta<=d;q<=meta;end
endmodule
