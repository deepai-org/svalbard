module pt_frame_tx(input wire clk,rst_n,mode8,
 input wire[9:0]wire_data,iq_data,input wire[6:0]wire_count,input wire[5:0]iq_count,
 output wire wire_pop,iq_pop,output reg[9:0]out_word);
 `include "pt_schedule.vh"
 reg[9:0]banks[0:127];reg active;reg[5:0]pos,seq;
 reg[5:0]wc[0:1],qc[0:1];reg[5:0]leftw,leftq;reg[15:0]crc;
 reg[2:0]training;wire[1:0]own=owner(mode8,pos);
 wire[29:0]header={8'b0,4'b0,seq,qc[active],wc[active]};
 `include "pt_crc.vh"
 assign wire_pop=training==4&&pos>=3&&pos<=61&&own==1&&leftw!=0;
 assign iq_pop=training==4&&pos>=3&&pos<=61&&own==2&&leftq!=0;
 always @* begin
  out_word=0;
  if(training<4)case(training)0:out_word=10'h3a5;1:out_word=10'h05a;2:out_word=10'h2d3;3:out_word=10'h12c;default:out_word=0;endcase
  else case(pos)
   0:out_word=header[9:0];1:out_word=header[19:10];2:out_word=header[29:20];
   62:out_word=crc[9:0];63:out_word={4'ha,crc[15:10]};
   default:out_word=banks[{active,pos}];
  endcase
 end
 integer j;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin active<=0;pos<=0;seq<=0;crc<=16'hffff;training<=0;leftw<=0;leftq<=0;wc[0]<=0;wc[1]<=0;qc[0]<=0;qc[1]<=0;
   for(j=0;j<128;j=j+1)banks[j]<=0;
  end else if(training<4)training<=training+1'b1;
  else begin
   if(pos==0)begin
    wc[!active]<=wire_count>(mode8?52:33)?(mode8?52:33):wire_count;
    qc[!active]<=iq_count>(mode8?7:25)?(mode8?7:25):iq_count;
    leftw<=wire_count>(mode8?52:33)?(mode8?52:33):wire_count;
    leftq<=iq_count>(mode8?7:25)?(mode8?7:25):iq_count;
   end
   if(pos>=3&&pos<=61)begin
    banks[{!active,pos}]<=wire_pop?wire_data:iq_pop?iq_data:10'b0;
    if(wire_pop)leftw<=leftw-1'b1;if(iq_pop)leftq<=leftq-1'b1;
   end
   if(pos<62)crc<=step(crc,out_word);
   if(pos==63)begin crc<=16'hffff;active<=!active;seq<=seq+1'b1;end
   pos<=pos+1'b1;
  end
 end
endmodule

module pt_frame_rx(input wire clk,rst_n,mode8,input wire[9:0]in_word,
 output wire[9:0]wire_data,iq_data,output wire wire_valid,iq_valid,
 input wire wire_ready,iq_ready,output reg fault,locked,
 output reg command_valid,output reg[3:0]opcode,output reg[7:0]argument);
 `include "pt_schedule.vh"
 reg[9:0]banks[0:127];reg writebank,readbank,release_frame;
 reg[5:0]pos,rpos,expected_seq,leftw,leftq;reg[2:0]training;
 reg[29:0]header;reg[9:0]trailer_low;reg[15:0]crc;
 // Shift a predecoded schedule instead of decoding the slot counter on the
 // same path as valid/count updates. Mode is frozen while armed.
 reg[58:0]wire_slots,iq_slots;
 wire[1:0]own=wire_slots[0]?2'd1:iq_slots[0]?2'd2:2'd0;
 // Registered 16:1 subreads followed by an 8:1 group select. One extra
 // release cycle; the last pending word must still be checked for readiness.
 reg[9:0]read_chunks[0:7];reg[2:0]read_group;reg pending_wire,pending_iq;
 wire issue_wire=release_frame&&!fault&&own==1&&leftw!=0;
 wire issue_iq=release_frame&&!fault&&own==2&&leftq!=0;
 assign wire_data=read_chunks[read_group];assign iq_data=wire_data;
 assign wire_valid=pending_wire&&!fault;assign iq_valid=pending_iq&&!fault;
 integer chunk;
 always @(posedge clk)if(release_frame&&!fault)begin
  for(chunk=0;chunk<8;chunk=chunk+1)read_chunks[chunk]<=banks[chunk*16+rpos[3:0]];
 end
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin read_group<=0;pending_wire<=0;pending_iq<=0;end
  else begin read_group<={readbank,rpos[5:4]};pending_wire<=issue_wire;pending_iq<=issue_iq;end
 end
 `include "pt_crc.vh"
 wire command_good=(header[21:18]==0&&header[29:22]==0)||
  ((header[21:18]==1||header[21:18]==2)&&header[29:22]<=1);
 wire good=command_good&&(in_word[9:6]==4'ha)&&({in_word[5:0],trailer_low}==crc)&&
  header[17:12]==expected_seq&&header[5:0]<=(mode8?52:33)&&header[11:6]<=(mode8?7:25);
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin wire_slots<=0;iq_slots<=0;fault<=0;locked<=0;training<=0;pos<=0;expected_seq<=0;writebank<=0;readbank<=1;release_frame<=0;rpos<=0;leftw<=0;leftq<=0;header<=0;crc<=16'hffff;trailer_low<=0;command_valid<=0;opcode<=0;argument<=0;end
  else begin
   command_valid<=0;
   if(!locked&&!fault)begin
    case(training)
     0:if(in_word==10'h3a5)training<=1;
     1:if(in_word==10'h05a)training<=2;else training<=(in_word==10'h3a5) ? 1 : 0;
     2:if(in_word==10'h2d3)training<=3;else training<=(in_word==10'h3a5) ? 1 : 0;
     3:if(in_word==10'h12c)begin locked<=1;pos<=0;training<=0;end else training<=0;
     default:training<=0;
    endcase
   end else if(!fault)begin
    if(release_frame)begin
     begin
      wire_slots<=wire_slots>>1;iq_slots<=iq_slots>>1;
      if(issue_wire)leftw<=leftw-1'b1;if(issue_iq)leftq<=leftq-1'b1;
      if(rpos==61)release_frame<=0;else rpos<=rpos+1'b1;
     end
    end
    if(pos==0)header[9:0]<=in_word;
    if(pos==1)header[19:10]<=in_word;
    if(pos==2)header[29:20]<=in_word;
    if(pos>=3&&pos<=61)banks[{writebank,pos}]<=in_word;
    if(pos<62)crc<=step(crc,in_word);
    if(pos==62)trailer_low<=in_word;
    if(pos==63)begin
     crc<=16'hffff;
     if(!good)begin fault<=1;release_frame<=0;end
     else begin readbank<=writebank;writebank<=!writebank;release_frame<=1;rpos<=3;
      wire_slots<=slot_mask(mode8,1);iq_slots<=slot_mask(mode8,2);
      leftw<=header[5:0];leftq<=header[11:6];expected_seq<=expected_seq+1'b1;
      command_valid<=1;opcode<=header[21:18];argument<=header[29:22];
     end
    end
    pos<=pos+1'b1;
    // Check the output stage even after the last memory read was issued.
    if((wire_valid&&!wire_ready)||(iq_valid&&!iq_ready))begin
     fault<=1;release_frame<=0;command_valid<=0;
    end
   end
  end
 end
endmodule
