// Word-at-a-time FPGA peer used to check the paired chip implementation.
// Production header encoding is shared through rtl/pt_dense_header.sv.
module pt_dense_tx(input wire clk,rst_n,payload_iq,
 input wire[9:0]wire_data,iq_data,input wire[6:0]wire_count,input wire[5:0]iq_count,
 input wire[3:0]opcode,input wire[7:0]argument,
 output wire wire_pop,iq_pop,output wire[9:0]out_word);
 reg[63:0]phase;
 reg[7:0]seq_low,seq_high;
 reg[5:0]encode_seq,pending_w,pending_q;
 reg payload_phase;
 wire has_wire,has_iq;wire[3:0]tail_wire,tail_iq;
 pt_dense_quota wire_quota(clk,rst_n,phase[63],payload_phase,pending_w,has_wire,tail_wire);
 pt_dense_quota iq_quota(clk,rst_n,phase[63],payload_phase,pending_q,has_iq,tail_iq);
 function automatic[2:0]encode8(input[7:0]onehot);
 begin encode8={|onehot[7:4],onehot[2]|onehot[3]|onehot[6]|onehot[7],
               onehot[1]|onehot[3]|onehot[5]|onehot[7]};end
 endfunction
 reg[11:0]pending_command;
 reg[6:0]raw_w,raw_q;reg[3:0]raw_reserved_w,raw_reserved_q;
 reg[4:0]low_w,low_q;reg[3:0]high_w,high_q,lower_w,lower_q;
 wire[6:0]credit_w={high_w[2:0],lower_w},credit_q={high_q[2:0],lower_q};
 reg[39:0]header_shift;wire[39:0]packet;
 pt_dense_header encoder(clk,{pending_command[7:0],pending_command[11:8],encode_seq,pending_q,pending_w},packet);
 assign wire_pop=rst_n&&payload_phase&&has_wire;
 assign iq_pop=rst_n&&payload_phase&&has_iq;
 assign out_word=(|phase[3:0])?header_shift[9:0]:phase[4]?10'h2d3:
                 wire_pop?wire_data:iq_pop?iq_data:10'd0;
 // Continuous short arithmetic stages. At word 56 at most eight advertised
 // words remain; four bits hold that reservation exactly. Snapshot subtraction
 // removes ALL remaining pops, including the pop on the snapshot edge.
 always @(posedge clk)begin
  encode_seq<={seq_low[7]?encode8({seq_high[6:0],seq_high[7]}):encode8(seq_high),
               encode8({seq_low[6:0],seq_low[7]})};
  low_w<={1'b0,raw_w[3:0]}-{1'b0,raw_reserved_w};
  low_q<={1'b0,raw_q[3:0]}-{1'b0,raw_reserved_q};
  high_w<={1'b0,raw_w[6:4]}-low_w[4];lower_w<=low_w[3:0];
  high_q<={1'b0,raw_q[6:4]}-low_q[4];lower_q<=low_q[3:0];
 end
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   phase<=64'd1;seq_low<=1;seq_high<=1;payload_phase<=0;pending_w<=0;pending_q<=0;
   pending_command<=0;header_shift<=40'ha000000000;
   raw_w<=0;raw_q<=0;raw_reserved_w<=0;raw_reserved_q<=0;
  end else begin
   phase<={phase[62:0],phase[63]};
   if(phase[4])payload_phase<=1;
   if(phase[63])payload_phase<=0;
   if(|phase[2:0])header_shift<=header_shift>>10;
   // Reserve, subtract, clamp, encode and publish before the next header.
   // Frame zero is empty; later counts/commands share this one snapshot.
   if(phase[56])begin
    raw_w<=wire_count;raw_q<={1'b0,iq_count};raw_reserved_w<=tail_wire;raw_reserved_q<=tail_iq;
    pending_command<={opcode,argument};
   end
   if(phase[59])begin
    pending_w<=payload_iq||high_w[3]?0:credit_w>59?6'd59:credit_w[5:0];
    pending_q<=!payload_iq||high_q[3]?0:credit_q>59?6'd59:credit_q[5:0];
   end
   if(phase[63])begin
    seq_low<={seq_low[6:0],seq_low[7]};
    if(seq_low[7])seq_high<={seq_high[6:0],seq_high[7]};
    header_shift<=packet;
   end
  end
 end
endmodule

module pt_dense_quota(input wire clk,rst_n,load,shift,input wire[5:0]count,
 output wire available,output wire[3:0]tail);
 reg[58:0]remaining,next_mask;
 reg[7:0]lo_gt,hi_gt,hi_eq;
 genvar i;
 generate for(i=0;i<8;i=i+1)begin:decode
  always @(posedge clk)begin
   lo_gt[i]<=count[2:0]>i;hi_gt[i]<=count[5:3]>i;hi_eq[i]<=count[5:3]==i;
  end
 end
 for(i=0;i<59;i=i+1)begin:mask
  always @(posedge clk)next_mask[i]<=hi_gt[i/8]||(hi_eq[i/8]&&lo_gt[i%8]);
 end endgenerate
 always @(posedge clk or negedge rst_n)
  if(!rst_n)remaining<=0;
  else if(load)remaining<=next_mask;
  else if(shift)remaining<=remaining>>1;
 assign available=remaining[0];
 wire[7:0]last=remaining[7:0]&~{1'b0,remaining[7:1]};
 assign tail={last[7],|last[6:3],last[1]|last[2]|last[5]|last[6],last[0]|last[2]|last[4]|last[6]};
endmodule

module pt_dense_rx(input wire clk,rst_n,payload_iq,input wire[9:0]in_word,
 input wire wire_ready,iq_ready,output wire[9:0]data,
 output wire wire_valid,iq_valid,output reg command_valid,fault,
 output reg[3:0]opcode,output reg[7:0]argument);
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
 wire semantics_good=(payload_iq?(decoded[5:0]==0&&decoded[11:6]<=59):
     (decoded[11:6]==0&&decoded[5:0]<=59))&&decoded[17:12]==expected_seq&&
     ((decoded[21:18]==0&&decoded[29:22]==0)||((decoded[21:18]==1||decoded[21:18]==2)&&decoded[29:22]<=1));
 assign data=in_word;
 assign wire_valid=rst_n&&!fault&&pos>=5&&leftw!=0&&wire_ready;
 assign iq_valid=rst_n&&!fault&&pos>=5&&leftq!=0&&iq_ready;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   header<=0;pos<=0;expected_seq<=0;leftw<=0;leftq<=0;
   command_valid<=0;fault<=0;opcode<=0;argument<=0;
  end else begin
   command_valid<=0;
   if(!fault)begin
    case(pos)
     0:header[9:0]<=in_word;
     1:header[19:10]<=in_word;
     2:header[29:20]<=in_word;
     3:header[39:30]<=in_word;
     4:if(header_good&&semantics_good)begin
       leftw<=decoded[5:0];leftq<=decoded[11:6];opcode<=decoded[21:18];argument<=decoded[29:22];command_valid<=1;
      end else fault<=1;
     default:begin
      if(leftw!=0)begin if(!wire_ready)fault<=1;else leftw<=leftw-1'b1;end
      if(leftq!=0)begin if(!iq_ready)fault<=1;else leftq<=leftq-1'b1;end
     end
    endcase
    pos<=pos+1'b1;if(pos==63)expected_seq<=expected_seq+1'b1;
   end
  end
 end
endmodule

module pt_dense_link_tx(input wire clk,rst_n,payload_iq,
 input wire[9:0]wire_data,iq_data,input wire[6:0]wire_count,input wire[5:0]iq_count,
 input wire[3:0]opcode,input wire[7:0]argument,
 output wire wire_pop,iq_pop,output reg[9:0]out_word);
 reg[3:0]training;wire running=training==8;
 wire[9:0]payload_word;wire wp,qp;
 pt_dense_tx payload(clk,rst_n&&running,payload_iq,wire_data,iq_data,wire_count,iq_count,opcode,argument,wp,qp,payload_word);
 assign wire_pop=running&&wp;assign iq_pop=running&&qp;
 always @(posedge clk or negedge rst_n)
  if(!rst_n)training<=0;else if(!running)training<=training+1'b1;
 always @*case(training)
  0:out_word=10'h3a5;1:out_word=10'h05a;2:out_word=10'h2d3;3:out_word=10'h12c;
  4:out_word=10'h369;5:out_word=10'h096;6:out_word=10'h21e;7:out_word=10'h1e1;
  default:out_word=payload_word;
 endcase
endmodule

module pt_dense_link_rx(input wire clk,rst_n,payload_iq,input wire[9:0]in_word,
 input wire wire_ready,iq_ready,output wire[9:0]data,
 output wire wire_valid,iq_valid,command_valid,fault,output reg locked,
 output wire[3:0]opcode,output wire[7:0]argument);
 reg[2:0]matched;reg[9:0]wait_count;reg acquisition_fault;
 wire payload_fault;reg[9:0]expected;
 assign fault=acquisition_fault||payload_fault;
 pt_dense_rx payload(clk,rst_n&&locked,payload_iq,in_word,wire_ready,iq_ready,data,wire_valid,iq_valid,command_valid,payload_fault,opcode,argument);
 always @*case(matched)
  0:expected=10'h3a5;1:expected=10'h05a;2:expected=10'h2d3;3:expected=10'h12c;
  4:expected=10'h369;5:expected=10'h096;6:expected=10'h21e;7:expected=10'h1e1;
 endcase
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin matched<=0;wait_count<=0;acquisition_fault<=0;locked<=0;end
  else if(!locked&&!acquisition_fault)begin
   if(in_word==expected&&matched==7)begin locked<=1;matched<=0;end
   else if(wait_count==1023)acquisition_fault<=1;
   else begin
    wait_count<=wait_count+1'b1;
    if(in_word==expected)matched<=matched+1'b1;
    else matched<=(in_word==10'h3a5)?3'd1:3'd0;
   end
  end
 end
endmodule
