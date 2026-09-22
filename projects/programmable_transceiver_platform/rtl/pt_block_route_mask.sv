// Caller supplies disjoint payload schedule masks, already excluding headers.
module pt_block_route_mask(input wire allow_payload,input wire[7:0]wire_slots,iq_slots,
 input wire[79:0]words,input wire[5:0]left_wire,left_iq,
 output wire[79:0]wire_words,iq_words,output wire[3:0]wire_count,iq_count,
 output reg[5:0]next_wire,next_iq);
 reg[7:0]wm,qm;integer lane;
 always @*begin
  wm=0;qm=0;next_wire=left_wire;next_iq=left_iq;
  for(lane=0;lane<8;lane=lane+1)begin
   if(allow_payload&&wire_slots[lane]&&next_wire!=0)begin wm[lane]=1;next_wire=next_wire-1'b1;end
   if(allow_payload&&iq_slots[lane]&&next_iq!=0)begin qm[lane]=1;next_iq=next_iq-1'b1;end
  end
 end
 pt_lane_compact wired(words,wm,wire_words,wire_count);
 pt_lane_compact iq(words,qm,iq_words,iq_count);
endmodule
