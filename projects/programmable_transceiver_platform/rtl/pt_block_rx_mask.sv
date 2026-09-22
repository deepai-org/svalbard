// Pipelined aligned RX candidate: input capture/validation then beat commit.
// Transfer strobes and command fields are sampled on the accepting clock edge.
module pt_block_rx_mask(input wire clk,rst_n,mode8,in_valid,input wire[79:0]words,
 input wire wire_ready,iq_ready,command_ready,output wire[79:0]wire_words,iq_words,
 output wire[3:0]wire_count,iq_count,output wire wire_valid,iq_valid,
 output wire command_valid,output wire[3:0]opcode,output wire[7:0]argument,
 output reg fault);
 `include "pt_schedule.vh"
 function automatic[7:0]mask_for(input mode,input[2:0]b,input[1:0]kind);
 integer i,pos;begin
  mask_for=0;
  for(i=0;i<8;i=i+1)begin
   pos=b*8+i;
   if(pos>=5)mask_for[i]=(owner(mode,6'(pos-2))==kind);
  end
 end endfunction
 reg[7:0]wire_slots,iq_slots;
 reg[2:0]beat,input_beat;reg[5:0]sequence_id,leftw,leftq;
 reg stage_valid,stage_good;reg[79:0]stage_words;
 reg[5:0]stage_wc,stage_qc;reg[3:0]stage_op;reg[7:0]stage_arg;
 wire good;wire[5:0]wc,qc,nw,nq;wire[3:0]op;wire[7:0]arg;
 pt_block_header header(words[49:0],mode8,sequence_id,good,wc,qc,op,arg);
 wire allowed=rst_n&&!fault&&stage_valid&&(beat!=0||stage_good);
 wire[79:0]wdata,qdata;wire[3:0]wn,qn;
 pt_block_route_mask route(allowed,wire_slots,iq_slots,stage_words,beat==0?stage_wc:leftw,beat==0?stage_qc:leftq,wdata,qdata,wn,qn,nw,nq);
 wire capacity=(wn==0||wire_ready)&&(qn==0||iq_ready)&&(beat!=0||command_ready);
 wire commit=allowed&&capacity;
 assign wire_valid=commit&&wn!=0;assign iq_valid=commit&&qn!=0;
 assign wire_words=commit?wdata:80'd0;assign iq_words=commit?qdata:80'd0;
 assign wire_count=commit?wn:4'd0;assign iq_count=commit?qn:4'd0;
 assign command_valid=commit&&beat==0;
 assign opcode=command_valid?stage_op:4'd0;assign argument=command_valid?stage_arg:8'd0;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   beat<=0;input_beat<=0;sequence_id<=0;leftw<=0;leftq<=0;
   fault<=0;stage_valid<=0;stage_good<=0;
  end else begin
   stage_valid<=in_valid&&!fault;
   if(in_valid&&!fault)begin
    wire_slots<=mask_for(mode8,input_beat,1);iq_slots<=mask_for(mode8,input_beat,2);
    stage_words<=words;beat<=input_beat;stage_good<=good;
    stage_wc<=wc;stage_qc<=qc;stage_op<=op;stage_arg<=arg;
    input_beat<=input_beat+1'b1;
    if(input_beat==7)sequence_id<=sequence_id+1'b1;
   end
   if(stage_valid&&!fault)begin
    if(!allowed||!capacity)begin fault<=1;stage_valid<=0;end
    else begin leftw<=nw;leftq<=nq;end
   end
  end
 end
endmodule
