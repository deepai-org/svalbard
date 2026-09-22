// Rank scheduled lanes independently of the remaining-count subtraction.
module pt_block_route_rank(input wire allow_payload,input wire[7:0]wire_slots,iq_slots,
 input wire[79:0]words,input wire[5:0]left_wire,left_iq,
 output wire[79:0]wire_words,iq_words,output wire[3:0]wire_count,iq_count,
 output wire[5:0]next_wire,next_iq);
 function automatic[3:0]prefix(input[7:0]mask,input integer stop);
 integer j;begin prefix=0;for(j=0;j<8;j=j+1)if(j<stop)prefix=prefix+{3'b0,mask[j]};end
 endfunction
 wire[7:0]wm,qm;
 genvar lane;
 generate for(lane=0;lane<8;lane=lane+1)begin:rank_lane
  assign wm[lane]=allow_payload&&wire_slots[lane]&&(left_wire>prefix(wire_slots,lane));
  assign qm[lane]=allow_payload&&iq_slots[lane]&&(left_iq>prefix(iq_slots,lane));
 end endgenerate
 wire[3:0]wt=prefix(wire_slots,8),qt=prefix(iq_slots,8);
 wire[5:0]usedw=allow_payload?(left_wire<wt?left_wire:{2'b0,wt}):6'd0;
 wire[5:0]usedq=allow_payload?(left_iq<qt?left_iq:{2'b0,qt}):6'd0;
 assign next_wire=left_wire-usedw,next_iq=left_iq-usedq;
 pt_lane_compact wired(words,wm,wire_words,wire_count);
 pt_lane_compact iq(words,qm,iq_words,iq_count);
endmodule
