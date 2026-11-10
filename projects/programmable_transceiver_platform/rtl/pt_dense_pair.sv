// Two chronological ten-bit words per engine clock. The fast pin launch and
// capture boundary remains ten bits; an engine clock is two host-word periods.
// Stopped-only payload_iq selects the sole FIFO owner. Each FIFO presents a
// twenty-bit pair and its available pair count, with registered FWFT data.
module pt_dense_pair_tx(input wire clk,rst_n,payload_iq,
 input wire[19:0]wire_data,iq_data,input wire[6:0]wire_pairs,iq_pairs,
 input wire[3:0]opcode,input wire[7:0]argument,
 output wire wire_pop,iq_pop,output wire[19:0]out_pair);
 reg[4:0]beat;reg[5:0]seq,left,pending;
 reg[9:0]held;reg have_held;
 reg[7:0]raw_count;reg[5:0]raw_left;
 reg[4:0]low_difference,high_difference;reg[3:0]low_delayed;
 reg[11:0]pending_command;
 reg[39:0]header;
 reg guard_phase,payload_phase;
 reg have_one,have_two;
 reg reserve_phase,clamp_phase,publish_phase;
 reg header_phase,header_low_phase;
 wire[19:0]source=payload_iq?iq_data:wire_data;
 wire[6:0]pairs=payload_iq?iq_pairs:wire_pairs;
 wire[7:0]available={pairs,1'b0}+have_held;
 wire[6:0]credit={high_difference[2:0],low_delayed};
 wire[39:0]encoded;
 // pending/seq/command are stable from the clamp edge, four clocks before publish.
 pt_dense_header #(.ALIGN(0)) encoder(clk,{pending_command[7:0],pending_command[11:8],6'(seq+1'b1),
                       payload_iq?pending:6'd0,payload_iq?6'd0:pending},encoded);
 wire[1:0]take=guard_phase?(have_one?1:0):payload_phase?(have_two?2:have_one?1:0):0;
 // Reset clears both phase and availability registers asynchronously. Do
 // not put the global reset tree in the steady-state FIFO request path.
 wire pop=(guard_phase&&have_one&&!have_held)||
          (payload_phase&&(have_two||(have_one&&!have_held)));
 assign wire_pop=pop&&!payload_iq;
 assign iq_pop=pop&&payload_iq;
 wire[9:0]first=have_held?held:source[9:0];
 wire[9:0]second=have_held?source[9:0]:source[19:10];
 assign out_pair=header_phase?header[19:0]:
                 guard_phase?{take!=0?first:10'd0,10'h2d3}:
                 {take==2?second:10'd0,take!=0?first:10'd0};
 always @(posedge clk)begin
  low_difference<={1'b0,raw_count[3:0]}-{1'b0,raw_left[3:0]};
  high_difference<={1'b0,raw_count[7:4]}-{3'd0,raw_left[5:4]}-low_difference[4];
  low_delayed<=low_difference[3:0];
 end
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   beat<=0;seq<=0;left<=0;pending<=0;held<=0;have_held<=0;
   raw_count<=0;raw_left<=0;pending_command<=0;header<=40'ha000000000;
   guard_phase<=0;payload_phase<=0;
   have_one<=0;have_two<=0;
   reserve_phase<=0;clamp_phase<=0;publish_phase<=0;
   header_phase<=1;header_low_phase<=1;
  end else begin
   beat<=beat+1'b1;
   guard_phase<=beat==1;payload_phase<=beat>=2&&beat!=31;
   reserve_phase<=beat==23;clamp_phase<=beat==26;publish_phase<=beat==30;
   header_phase<=publish_phase||header_low_phase;header_low_phase<=publish_phase;
   if(header_low_phase)header<=header>>20;
   // Capture the unused high word even when a whole pair is consumed. It
   // is ignored while have_held=0, and avoids a late alignment XOR on D.
   if(pop)held<=source[19:10];
   if(take==1)have_held<=!have_held;
   if(guard_phase)begin
    if(have_one)begin left[0]<=!left[0];left[5:1]<=left[5:1]-!left[0];end
    else left<=0;
   end
   if(payload_phase)begin
    if(have_two)left[5:1]<=left[5:1]-1'b1;else left<=0;
   end
   if(guard_phase)begin have_one<=have_two;have_two<=(|left[5:2])||(&left[1:0]);end
   if(payload_phase)begin
    have_one<=(|left[5:2])||(&left[1:0]);have_two<=|left[5:2];
   end
   // Count both newly visible FIFO pairs and the held odd word. Subtract
   // every current-frame reservation, including this edge's transfer.
   if(reserve_phase)begin raw_count<=available;raw_left<=left;pending_command<={opcode,argument};end
   if(clamp_phase)pending<=high_difference[4]?0:
       high_difference[3]||credit>59?6'd59:credit[5:0];
   if(publish_phase)begin
    left<=pending;have_one<=|pending;have_two<=|pending[5:1];seq<=seq+1'b1;header<=encoded;
   end
  end
 end
endmodule

// Input is word-pair aligned. One pair of input buffering allows two short
// parity stages before guard validation. No payload can escape a bad header.
// count=1 places its one chronological payload word in data[9:0].
module pt_dense_pair_rx(input wire clk,rst_n,payload_iq,input wire[19:0]in_pair,
 input wire wire_ready,iq_ready,output wire[19:0]data,
 output wire[1:0]wire_count,iq_count,output wire command_valid,
 output reg fault,output wire[3:0]opcode,output wire[7:0]argument);
 reg[4:0]raw_beat,beat;reg input_valid;
 reg[19:0]input_pair;reg[39:0]header;
 reg[5:0]expected_seq,left;
 reg[27:0]parts;reg parts_valid,parts_high;
 reg[6:0]check_low;
 reg parity_good,metadata_good;
 reg guard_phase,payload_phase;
 reg[5:0]initial_left;reg empty_header;
 reg have_one,have_two;
 function automatic[11:0]counts(input[19:0]lower);
 integer p,d;begin
  counts=0;d=0;
  for(p=1;p<=20;p=p+1)if((p&(p-1))!=0)begin
   if(d<12)counts[d]=lower[p-1];d=d+1;
  end
 end endfunction
 wire[11:0]early_counts=counts(input_pair);
 wire[5:0]early_advertised=payload_iq?early_counts[11:6]:early_counts[5:0];
 function automatic[6:0]check5(input[4:0]value,input integer base);
 integer b,p,k;begin
  check5=0;
  for(b=0;b<5;b=b+1)begin
   p=base+b+1;
   if(p<=36)for(k=0;k<6;k=k+1)if((p&(1<<k))!=0)check5[k]=check5[k]^value[b];
   if(p<=37)check5[6]=check5[6]^value[b];
  end
 end endfunction
 genvar group;
 generate for(group=0;group<4;group=group+1)begin:parity_groups
  always @(posedge clk)parts[group*7+:7]<=raw_beat[0]?
       check5(in_pair[group*5+:5],20+group*5):check5(in_pair[group*5+:5],group*5);
 end endgenerate
 wire[6:0]combined=parts[6:0]^parts[13:7]^parts[20:14]^parts[27:21];
 function automatic[29:0]decode(input[39:0]value);
 integer p,d;begin
  decode=0;d=0;
  for(p=1;p<=36;p=p+1)if((p&(p-1))!=0)begin decode[d]=value[p-1];d=d+1;end
 end endfunction
 wire[29:0]decoded=decode(header);
 wire[29:0]incoming=decode({input_pair,header[19:0]});
 assign opcode=decoded[21:18];assign argument=decoded[29:22];
 wire[5:0]advertised=payload_iq?incoming[11:6]:incoming[5:0];
 wire semantics=advertised<=59&&(payload_iq?incoming[5:0]==0:incoming[11:6]==0)&&
     incoming[17:12]==expected_seq&&((incoming[21:18]==0&&incoming[29:22]==0)||
       ((incoming[21:18]==1||incoming[21:18]==2)&&incoming[29:22]<=1));
 wire good=parity_good&&metadata_good&&input_pair[9:0]==10'h2d3;
 wire guard=guard_phase;
 wire payload=payload_phase;
 wire[1:0]amount=guard?(good&&!empty_header?1:0):payload?(have_two?2:have_one?1:0):0;
 wire ready=payload_iq?iq_ready:wire_ready;
 wire accepted=!fault&&ready;
 assign wire_count=accepted&&!payload_iq?amount:0;
 assign iq_count=accepted&&payload_iq?amount:0;
 assign data=guard?{10'd0,input_pair[19:10]}:input_pair;
 // Command and first payload word are accepted on the same engine edge,
 // after all metadata checks. The parent samples decoded fields only here.
 assign command_valid=!fault&&guard&&good;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   raw_beat<=0;beat<=0;input_valid<=0;input_pair<=0;header<=0;expected_seq<=0;left<=0;
   parts_valid<=0;parts_high<=0;check_low<=0;fault<=0;
   parity_good<=0;metadata_good<=0;
   guard_phase<=0;payload_phase<=0;
   initial_left<=0;empty_header<=1;
   have_one<=0;have_two<=0;
  end else begin
   raw_beat<=raw_beat+1'b1;input_valid<=1;input_pair<=in_pair;
   parts_valid<=raw_beat<2;parts_high<=raw_beat[0];
   if(parts_valid&&!parts_high)check_low<=combined;
   // Parsing may continue after fault, but accepted and command_valid remain
   // blocked by its sticky latch. Keep fault off the header clock-enable tree.
   if(input_valid)begin
    beat<=beat+1'b1;
    guard_phase<=beat==1;payload_phase<=beat>=2&&beat!=31;
    if(beat==0)begin
     header[19:0]<=input_pair;initial_left<=early_advertised-1'b1;empty_header<=early_advertised==0;
    end
    if(beat==1)begin
     header[39:20]<=input_pair;
     // Finish validation while capturing the second header pair. Its
     // result reaches the guard through a single registered flag.
     parity_good<=(check_low^combined)==0;
     metadata_good<=semantics&&input_pair[19:17]==3'b101;
    end
    if(guard)begin
     // Counts may update speculatively: a bad header/refusal latches fault
     // and blocks every effect. Parity must not sit ahead of subtraction.
     left<=empty_header?0:initial_left;
     have_one<=!empty_header&&(|initial_left);have_two<=!empty_header&&(|initial_left[5:1]);
     if(!good||(amount!=0&&!ready))fault<=1;
    end else if(payload)begin
     if(have_two)left[5:1]<=left[5:1]-1'b1;else left<=0;
     have_one<=(|left[5:2])||(&left[1:0]);have_two<=|left[5:2];
     if(amount!=0&&!ready)fault<=1;
    end
    if(beat==31)expected_seq<=expected_seq+1'b1;
   end
  end
 end
endmodule

module pt_dense_pair_link_tx(input wire clk,rst_n,payload_iq,
 input wire[19:0]wire_data,iq_data,input wire[6:0]wire_pairs,iq_pairs,
 input wire[3:0]opcode,input wire[7:0]argument,
 output wire wire_pop,iq_pop,output reg[19:0]out_pair);
 reg[2:0]training;wire running=training==4;
 wire[19:0]payload;wire wp,qp;
 pt_dense_pair_tx engine(clk,rst_n&&running,payload_iq,wire_data,iq_data,wire_pairs,iq_pairs,opcode,argument,wp,qp,payload);
 // The engine stays reset throughout training; cleared phase/credit state
 // already prevents every pop until an actual payload reservation exists.
 assign wire_pop=wp;assign iq_pop=qp;
 always @(posedge clk or negedge rst_n)if(!rst_n)training<=0;else if(!running)training<=training+1'b1;
 always @*case(training)
  0:out_pair={10'h05a,10'h3a5};1:out_pair={10'h12c,10'h2d3};
  2:out_pair={10'h096,10'h369};3:out_pair={10'h1e1,10'h21e};
  default:out_pair=payload;
 endcase
endmodule
