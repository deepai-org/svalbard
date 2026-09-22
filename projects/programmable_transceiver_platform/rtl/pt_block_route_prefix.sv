// Compact scheduled words first, then retain the permitted prefix.
module pt_block_route_prefix(input wire allow_payload,input wire[7:0]wire_slots,iq_slots,
 input wire[79:0]words,input wire[5:0]left_wire,left_iq,
 output wire[79:0]wire_words,iq_words,output wire[3:0]wire_count,iq_count,
 output wire[5:0]next_wire,next_iq);
 wire[79:0]all_wire,all_iq;wire[3:0]wt,qt;
 pt_lane_compact wired(words,wire_slots,all_wire,wt);
 pt_lane_compact iq(words,iq_slots,all_iq,qt);
 assign wire_count=allow_payload?(left_wire<wt?left_wire[3:0]:wt):4'd0;
 assign iq_count=allow_payload?(left_iq<qt?left_iq[3:0]:qt):4'd0;
 assign next_wire=left_wire-{2'b0,wire_count},next_iq=left_iq-{2'b0,iq_count};
 genvar lane;
 generate for(lane=0;lane<8;lane=lane+1)begin:trim
  assign wire_words[lane*10+:10]=(lane<wire_count)?all_wire[lane*10+:10]:10'd0;
  assign iq_words[lane*10+:10]=(lane<iq_count)?all_iq[lane*10+:10]:10'd0;
 end endgenerate
endmodule
