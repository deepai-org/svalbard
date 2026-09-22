// Combinational payload routing only; caller owns header validation/frame state.
module pt_block_route(input wire mode8,allow_payload,input wire[2:0]beat,
 input wire[79:0]words,input wire[5:0]left_wire,left_iq,
 output wire[79:0]wire_words,iq_words,output wire[3:0]wire_count,iq_count,
 output reg[5:0]next_wire,next_iq);
 `include "pt_schedule.vh"
 reg[7:0]wire_mask,iq_mask;integer lane,pos;
 always @*begin
  wire_mask=0;iq_mask=0;next_wire=left_wire;next_iq=left_iq;
  for(lane=0;lane<8;lane=lane+1)begin
   pos=beat*8+lane;
   if(allow_payload&&pos>=5)begin
    case(owner(mode8,6'(pos-2)))
     1:if(next_wire!=0)begin wire_mask[lane]=1;next_wire=next_wire-1'b1;end
     2:if(next_iq!=0)begin iq_mask[lane]=1;next_iq=next_iq-1'b1;end
     default:begin end
    endcase
   end
  end
 end
 pt_lane_compact wired(words,wire_mask,wire_words,wire_count);
 pt_lane_compact iq(words,iq_mask,iq_words,iq_count);
endmodule
