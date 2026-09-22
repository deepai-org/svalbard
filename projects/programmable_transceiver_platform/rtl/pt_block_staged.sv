// Candidate ingress holding register plus block CDC and receiving elasticity.
module pt_block_staged(
 input wire wr_clk,rd_clk,rst_n,
 input wire[79:0]wr_data,input wire[3:0]wr_words,
 input wire wr_valid,output wire wr_ready,
 output wire[79:0]rd_data,output wire[3:0]rd_words,
 output wire rd_valid,input wire rd_ready,output wire wr_fault);
 (* async_reg="true" *) reg[1:0] release_write;
 always @(posedge wr_clk or negedge rst_n)
  if(!rst_n)release_write<=0;else release_write<={release_write[0],1'b1};
 wire active=release_write[1];
 reg[83:0]held;reg held_valid,bad_count;
 wire next_ready,next_fault;
 wire legal=wr_words>=1&&wr_words<=8;
 assign wr_ready=active&&(!held_valid||next_ready);
 assign wr_fault=bad_count||next_fault;
 always @(posedge wr_clk or negedge active)
  if(!active)begin held_valid<=0;bad_count<=0;end
  else if(wr_ready)begin
   held_valid<=wr_valid&&legal;
   if(wr_valid&&legal)held<={wr_words,wr_data};
   if(wr_valid&&!legal)bad_count<=1;
  end
 pt_block_elastic link(.wr_clk(wr_clk),.rd_clk(rd_clk),.rst_n(rst_n),
  .wr_data(held[79:0]),.wr_words(held[83:80]),.wr_valid(active&&held_valid),
  .wr_ready(next_ready),.wr_fault(next_fault),.rd_data(rd_data),.rd_words(rd_words),
  .rd_valid(rd_valid),.rd_ready(rd_ready));
endmodule
