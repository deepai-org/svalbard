// Candidate v2 receiver. Input must already be word/frame aligned; reset starts
// expected_seq zero. No acquisition/CDC or payload error detection is implied.
module pt_stream_rx(input wire clk,rst_n,mode8,input wire[9:0]in_word,
 input wire wire_ready,iq_ready,output wire[9:0]data,
 output wire wire_valid,iq_valid,output reg command_valid,fault,
 output reg[3:0]opcode,output reg[7:0]argument);
 `include "pt_schedule.vh"
 reg[39:0]header;reg[5:0]pos,expected_seq,leftw,leftq;
 reg[29:0]decoded;reg[5:0]syndrome;integer p,d;
 always @*begin
  decoded=0;syndrome=0;d=0;
  for(p=1;p<=36;p=p+1)begin
   if(header[p-1])syndrome=syndrome^6'(p);
   if((p&(p-1))!=0)begin decoded[d]=header[p-1];d=d+1;end
  end
 end
 wire header_good=header[39:37]==3'b101&&syndrome==0&&(^header[36:0])==0&&in_word==10'h2d3;
 wire semantics_good=decoded[5:0]<=(mode8?52:33)&&decoded[11:6]<=(mode8?7:25)&&decoded[17:12]==expected_seq&&
 ((decoded[21:18]==0&&decoded[29:22]==0)||((decoded[21:18]==1||decoded[21:18]==2)&&decoded[29:22]<=1));
 // Load the fixed schedule once per accepted header. The low bits directly
 // drive transfer qualification; no slot-counter decode sits on FIFO writes.
 reg[58:0]wire_slots,iq_slots;
 function automatic[58:0]slot_mask(input mode,input[1:0]kind);
 integer k;begin for(k=0;k<59;k=k+1)slot_mask[k]=(owner(mode,6'(k+3))==kind);end endfunction
 // Combinational transfer strobes, sampled with in_word on this clock edge.
 // The continuously arriving source cannot stall: refused payload latches fault.
 assign data=in_word;
 assign wire_valid=rst_n&&!fault&&wire_slots[0]&&leftw!=0&&wire_ready;
 assign iq_valid=rst_n&&!fault&&iq_slots[0]&&leftq!=0&&iq_ready;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin wire_slots<=0;iq_slots<=0;header<=0;pos<=0;expected_seq<=0;leftw<=0;leftq<=0;command_valid<=0;fault<=0;opcode<=0;argument<=0;end
  else begin
   command_valid<=0;
   if(!fault)begin
    case(pos)
     0:header[9:0]<=in_word;
     1:header[19:10]<=in_word;
     2:header[29:20]<=in_word;
     3:header[39:30]<=in_word;
     4:if(header_good&&semantics_good)begin
       wire_slots<=slot_mask(mode8,1);iq_slots<=slot_mask(mode8,2);
       leftw<=decoded[5:0];leftq<=decoded[11:6];opcode<=decoded[21:18];argument<=decoded[29:22];command_valid<=1;
      end else fault<=1;
     default:begin
      wire_slots<=wire_slots>>1;iq_slots<=iq_slots>>1;
      if(wire_slots[0]&&leftw!=0)begin
       if(!wire_ready)fault<=1;
       else begin leftw<=leftw-1'b1;end
      end
      if(iq_slots[0]&&leftq!=0)begin
       if(!iq_ready)fault<=1;
       else begin leftq<=leftq-1'b1;end
      end
     end
    endcase
    pos<=pos+1'b1;if(pos==63)expected_seq<=expected_seq+1'b1;
   end
  end
 end
endmodule
