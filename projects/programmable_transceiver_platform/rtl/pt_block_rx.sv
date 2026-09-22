// Aligned eight-word v2 RX candidate. No input backpressure or acquisition.
// Transfer strobes and command fields are sampled on the accepting clock edge.
module pt_block_rx(input wire clk,rst_n,mode8,in_valid,input wire[79:0]words,
 input wire wire_ready,iq_ready,command_ready,output wire[79:0]wire_words,iq_words,
 output wire[3:0]wire_count,iq_count,output wire wire_valid,iq_valid,
 output wire command_valid,output wire[3:0]opcode,output wire[7:0]argument,
 output reg fault);
 reg[2:0]beat;reg[5:0]sequence_id,leftw,leftq;
 wire good;wire[5:0]wc,qc,nw,nq;wire[3:0]op;wire[7:0]arg;
 pt_block_header header(words[49:0],mode8,sequence_id,good,wc,qc,op,arg);
 wire allowed=rst_n&&!fault&&in_valid&&(beat!=0||good);
 wire[79:0]wdata,qdata;wire[3:0]wn,qn;
 pt_block_route route(mode8,allowed,beat,words,beat==0?wc:leftw,beat==0?qc:leftq,wdata,qdata,wn,qn,nw,nq);
 wire capacity=(wn==0||wire_ready)&&(qn==0||iq_ready)&&(beat!=0||command_ready);
 wire commit=allowed&&capacity;
 assign wire_valid=commit&&wn!=0;assign iq_valid=commit&&qn!=0;
 assign wire_words=commit?wdata:80'd0;assign iq_words=commit?qdata:80'd0;
 assign wire_count=commit?wn:4'd0;assign iq_count=commit?qn:4'd0;
 assign command_valid=commit&&beat==0;
 assign opcode=command_valid?op:4'd0;assign argument=command_valid?arg:8'd0;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin beat<=0;sequence_id<=0;leftw<=0;leftq<=0;fault<=0;end
  else if(in_valid&&!fault)begin
   if(!allowed||!capacity)fault<=1;
   else begin
    leftw<=nw;leftq<=nq;beat<=beat+1'b1;
    if(beat==7)sequence_id<=sequence_id+1'b1;
   end
  end
 end
endmodule
