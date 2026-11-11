// AC-1 transport framing at word/4: four chronological ten-bit words per
// engine clock (78.125 MHz at the 312.5 Mword/s host rate). Word 0 (earliest
// on the pins) is bits [9:0]. The frame is unchanged from the ten-bit codec
// (spec/streaming-transport-v2.md): 64 words = 16 quads; quad 0 is the
// protected 40-bit header (words 0..3), quad 1 is {w7,w6,w5,guard 0x2d3},
// quads 2..15 carry payload words 8..63. 3 + 14*4 = 59 payload words.
// Exclusive owner (payload_iq, stopped-only) selects the only source.

// ---------------------------------------------------------------------------
// Frame engine, D2H direction. The selected FIFO presents a registered FWFT
// head quad and a (conservative, registered) count of complete quads. Up to
// three words of a popped quad are held between beats/frames, left-aligned in
// `res`, so a popped head's top three words always become the new residual.
// Credit: at beat 9 the available words (4*quads + residual) minus every word
// still reserved for the current frame are snapshot (beat 11, barrier limit at 12); beats 13/14 subtract
// and clamp to 59; the one-stage header parity (pt_dense_header ALIGN=0 STAGES=1)
// settles at beat 15 and the header is sent at beat 0 straight from the encoder.
//
// Fast gain status (opcode4, RF ownership only; spec/streaming-transport-v2.md "Atomic RF gain
// metadata"). gain_commit (the H2D command was accepted) raises a barrier: frames then carry only
// samples taken before the new gain. Until the ingress side reports where the new-gain samples
// start (mk_seen, pre_quads = complete quads still ahead of that point in the ingress FIFO), the
// credit is limited to the words present at the commit (safe). When every older word is reserved,
// the next frame is the gain-status frame: opcode4, argument {gap[6], gain}, wc = gap[5:0] (the
// invalid/discarded pair count) and qc = its new-gain payload words; gain_echo pulses when it is
// published (end of beat 15).
module pt_quad_tx #(parameter CW=5)(input wire clk,rst_n,payload_iq,
 input wire[39:0]wire_data,iq_data,input wire[CW:0]wire_quads,iq_quads,
 input wire[3:0]opcode,input wire[7:0]argument,
 output wire wire_pop,iq_pop,output wire[39:0]out_quad,
 input wire gain_commit,input wire[6:0]gain_arg,input wire mk_seen,input wire[CW:0]pre_quads,
 input wire[6:0]gap,output reg gain_echo);
 reg[3:0]beat;reg[5:0]seq,left,pending,guard_left;
 reg[2:0]take;reg[1:0]rcnt;reg[29:0]res;
 reg[8:0]raw_count,raw_left;reg signed[9:0]credit;
 reg[11:0]pending_command;reg first;
 reg barrier,echo_next,bar_r,mk_r;reg[8:0]safe,before_r;reg[5:0]echo_wc;
 wire[39:0]head=payload_iq?iq_data:wire_data;
 wire[CW:0]quads=payload_iq?iq_quads:wire_quads;
 wire[39:0]encoded;
 // The header is taken straight from the encoder at beat 0: every encoder input is stable from
 // beat 14 (pending) through beat 0 of the next frame (seq increments after beat 0).
 pt_dense_header #(.ALIGN(0),.STAGES(1)) encoder(clk,{pending_command[7:0],pending_command[11:8],seq,
                       payload_iq?pending:6'd0,payload_iq?(echo_next?echo_wc:6'd0):pending},encoded);
 // words available now / words known to precede the new-gain samples
 wire[8:0]avail_words={1'b0,quads,2'b00}+rcnt;
 wire[8:0]before_words=mk_seen?{1'b0,pre_quads,2'b00}+rcnt:safe;
 // Words in chronological order: the rcnt held words, then the head quad.
 wire[69:0]cat={head,res};
 reg[39:0]avail;
 always @*case(rcnt)
  2'd0:avail=cat[69:30];2'd1:avail=cat[59:20];
  2'd2:avail=cat[49:10];default:avail=cat[39:0];
 endcase
 wire pop=take>{1'b0,rcnt};
 assign wire_pop=pop&&!payload_iq;
 assign iq_pop=pop&&payload_iq;
 wire guard=beat==4'd1;
 wire[39:0]keep={{10{take>3'd3}},{10{take>3'd2}},{10{take>3'd1}},{10{take>3'd0}}};
 wire[39:0]words=avail&keep;
 assign out_quad=beat==4'd0 ?(first?40'ha000000000:encoded):guard?{words[29:0],10'h2d3}:words;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   beat<=0;seq<=0;left<=0;pending<=0;guard_left<=0;take<=0;rcnt<=0;res<=0;
   raw_count<=0;raw_left<=0;credit<=0;pending_command<=0;first<=1;
   barrier<=0;echo_next<=0;bar_r<=0;mk_r<=0;safe<=0;before_r<=0;echo_wc<=0;gain_echo<=0;
  end else begin
   gain_echo<=0;
   if(gain_commit)begin barrier<=1;safe<=avail_words;end
   else if(barrier&&!mk_seen)safe<=safe-take;
   beat<=beat+1'b1;
   if(pop)res<=head[39:10];
   rcnt<=rcnt+(pop?3'd4:3'd0)-take;
   // left counts the reserved words of this frame before the current beat.
   case(beat)
    4'd0:begin
     first<=0;seq<=seq+1'b1;
     take<=left>=6'd3 ?3'd3:{1'b0,left[1:0]};
     guard_left<=left>=6'd3 ?left-6'd3:6'd0;
    end
    4'd1:begin
     left<=guard_left;
     take<=|guard_left[5:2]?3'd4:guard_left[2:0];
    end
    4'd15:begin
     left<=pending;take<=0;
     if(echo_next)begin barrier<=0;gain_echo<=1;end
    end
    default:begin
     left<=|left[5:2]?{left[5:2]-1'b1,left[1:0]}:6'd0;
     take<=|left[5:3]?3'd4:left[2]?{1'b0,left[1:0]}:3'd0;
    end
   endcase
   // credit snapshot (beat 11): available words, words still reserved for this frame and, under a
   // gain barrier, the words known to precede the new-gain samples; decided at beat 12
   if(beat==4'd11)begin
    raw_count<=avail_words;raw_left<={3'd0,left};before_r<=before_words;bar_r<=barrier;mk_r<=mk_seen;
   end
   if(beat==4'd12)begin
    if(bar_r&&mk_r&&before_r==raw_left)begin
     // every older word is in this frame: the next frame is the gain-status frame
     echo_next<=1;pending_command<={4'd4,gap[6],gain_arg};echo_wc<=gap[5:0];
    end else begin
     echo_next<=0;pending_command<={opcode,argument};
     if(bar_r&&before_r<raw_count)raw_count<=before_r;
    end
   end
   if(beat==4'd13)credit<=$signed({1'b0,raw_count})-$signed({1'b0,raw_left});
   if(beat==4'd14)pending<=credit<0?6'd0:credit>59?6'd59:credit[5:0];
  end
 end
endmodule

// ---------------------------------------------------------------------------
// Frame engine, H2D direction. Input quads are already word aligned. Header
// parity, tag, sequence, ownership, count and command legality are checked
// during header beat 0 and registered; the guard word is compared one beat
// early from the incoming quad. The guard beat then releases up to three
// payload words only if everything validated. A destination that cannot
// accept a released word latches fault (no backpressure). count=n places its
// n chronological payload words in data[10n-1:0].
module pt_quad_rx(input wire clk,rst_n,payload_iq,input wire[39:0]in_quad,
 input wire wire_ready,iq_ready,output wire[39:0]data,
 output wire[2:0]wire_count,iq_count,output wire command_valid,
 output reg fault,output reg[3:0]opcode,output reg[7:0]argument);
 reg[39:0]q;reg qv;reg[3:0]beat;
 reg[5:0]expected_seq,left,guard_left;reg[2:0]take,guard_take;
 reg header_ok,guard_ok;
 function automatic[29:0]decode(input[39:0]value);
 integer p,d;begin
  decode=0;d=0;
  for(p=1;p<=36;p=p+1)if((p&(p-1))!=0)begin decode[d]=value[p-1];d=d+1;end
 end endfunction
 function automatic[6:0]syndrome(input[39:0]value);
 integer p,k;begin
  syndrome=0;
  for(p=1;p<=37;p=p+1)begin
   if(p<=36)for(k=0;k<6;k=k+1)if((p&(1<<k))!=0)syndrome[k]=syndrome[k]^value[p-1];
   syndrome[6]=syndrome[6]^value[p-1];
  end
 end endfunction
 wire[29:0]fields=decode(q);
 wire[5:0]advertised=payload_iq?fields[11:6]:fields[5:0];
 wire[5:0]inactive=payload_iq?fields[5:0]:fields[11:6];
 wire[3:0]op=fields[21:18];wire[7:0]arg=fields[29:22];
 // opcode4 (fast gain): RF ownership only, no payload (wc = qc = 0), argument bit7 zero, PGA 0..16.
 wire legal=(op==0&&arg==0)||((op==1||op==2)&&arg<=1)||
            (op==4&&payload_iq&&advertised==0&&!arg[7]&&arg[4:0]<=5'd16);
 wire header_good=syndrome(q)==0&&q[39:37]==3'b101&&advertised<=59&&inactive==0&&
     fields[17:12]==expected_seq&&legal;
 wire header_beat=qv&&beat==4'd0,guard=qv&&beat==4'd1,payload=qv&&beat>=4'd2;
 wire good=header_ok&&guard_ok;
 wire[2:0]amount=guard?(good?guard_take:3'd0):payload?take:3'd0;
 wire ready=payload_iq?iq_ready:wire_ready;
 wire accepted=!fault&&ready;
 assign wire_count=accepted&&!payload_iq?amount:3'd0;
 assign iq_count=accepted&&payload_iq?amount:3'd0;
 assign data=guard?{10'd0,q[39:10]}:q;
 assign command_valid=!fault&&guard&&good;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   q<=0;qv<=0;beat<=0;expected_seq<=0;left<=0;guard_left<=0;take<=0;guard_take<=0;
   header_ok<=0;guard_ok<=0;fault<=0;opcode<=0;argument<=0;
  end else begin
   q<=in_quad;qv<=1;
   if(qv)begin
    beat<=beat+1'b1;
    if(header_beat)begin
     // Counts update speculatively; a bad header latches fault and blocks
     // every effect of this frame at the guard beat.
     header_ok<=header_good;guard_ok<=in_quad[9:0]==10'h2d3;
     opcode<=op;argument<=arg;
     guard_take<=advertised>=6'd3 ?3'd3:{1'b0,advertised[1:0]};
     guard_left<=advertised>=6'd3 ?advertised-6'd3:6'd0;
    end
    if(guard)begin
     left<=guard_left;take<=|guard_left[5:2]?3'd4:guard_left[2:0];
     if(!good||(amount!=0&&!ready))fault<=1;
    end else if(payload)begin
     left<=|left[5:2]?{left[5:2]-1'b1,left[1:0]}:6'd0;
     take<=|left[5:3]?3'd4:left[2]?{1'b0,left[1:0]}:3'd0;
     if(amount!=0&&!ready)fault<=1;
    end
    if(beat==4'd15)expected_seq<=expected_seq+1'b1;
   end
  end
 end
endmodule

// ---------------------------------------------------------------------------
// D2H link: two training quads (the ten-bit prefix 3A5 05A 2D3 12C 369 096
// 21E 1E1), then the engine starting with an empty frame. Registered output.
module pt_quad_link_tx #(parameter CW=5)(input wire clk,rst_n,payload_iq,
 input wire[39:0]wire_data,iq_data,input wire[CW:0]wire_quads,iq_quads,
 input wire[3:0]opcode,input wire[7:0]argument,
 output wire wire_pop,iq_pop,output wire[39:0]out_quad,
 input wire gain_commit,input wire[6:0]gain_arg,input wire mk_seen,input wire[CW:0]pre_quads,
 input wire[6:0]gap,output wire gain_echo);
 reg[1:0]training;reg running;
 wire[39:0]payload;
 pt_quad_tx #(.CW(CW)) engine(clk,rst_n&&running,payload_iq,wire_data,iq_data,wire_quads,iq_quads,
  opcode,argument,wire_pop,iq_pop,payload,gain_commit,gain_arg,mk_seen,pre_quads,gap,gain_echo);
 // Output: reset 0, training quads T0 and T1 on the two clocks after reset, then the engine.
 reg started;
 always @(posedge clk or negedge rst_n)
  if(!rst_n)begin training<=0;running<=0;started<=0;end
  else begin
   started<=1;
   if(started&&!running)training<=training+1'b1;
   running<=running||(started&&training==2'd1);
  end
 // Registered output (AC-1 ss32 timing): the framer's beat/count decode no longer feeds the host
 // link's XOR prefix in the same hcore cycle (one hcore of D2H latency, +40 FF).
 reg[39:0]oq;
 always @(posedge clk or negedge rst_n)
  if(!rst_n)oq<=40'd0;
  else oq<=!started?40'd0:running?payload:training==2'd0 ?{10'h12c,10'h2d3,10'h05a,10'h3a5}:
                                                         {10'h1e1,10'h21e,10'h096,10'h369};
 assign out_quad=oq;
endmodule

// ---------------------------------------------------------------------------
// H2D link: finite training acquisition in any of the four word rotations of
// the quad stream (the pad-edge 1:4 gearbox has no word alignment). Once
// locked the rotation is fixed until reset; payload is never searched.
module pt_quad_link_rx(input wire clk,rst_n,payload_iq,
 input wire[39:0]in_quad,input wire wire_ready,iq_ready,
 output wire[39:0]data,output wire[2:0]wire_count,iq_count,
 output wire command_valid,fault,output reg locked,
 output wire[3:0]opcode,output wire[7:0]argument);
 localparam[39:0]T0={10'h12c,10'h2d3,10'h05a,10'h3a5},T1={10'h1e1,10'h21e,10'h096,10'h369};
 reg[29:0]previous;reg[3:0]first_seen;reg[1:0]rotation;
 reg[7:0]wait_count;reg acquisition_fault;
 wire[69:0]cat={in_quad,previous};
 wire[39:0]shifted[0:3];
 assign shifted[0]=cat[69:30];assign shifted[1]=cat[59:20];
 assign shifted[2]=cat[49:10];assign shifted[3]=cat[39:0];
 // rotation is fixed after lock: a registered one-hot copy drives the 40-bit AND-OR select
 // directly (no decode in front of the fanout).
 reg[3:0]rot_oh;
 wire[39:0]aligned=({40{rot_oh[0]}}&shifted[0])|({40{rot_oh[1]}}&shifted[1])|
                   ({40{rot_oh[2]}}&shifted[2])|({40{rot_oh[3]}}&shifted[3]);
 wire[3:0]is_first,is_second;
 genvar k;
 generate for(k=0;k<4;k=k+1)begin:rotations
  assign is_first[k]=shifted[k]==T0;
  assign is_second[k]=first_seen[k]&&shifted[k]==T1;
 end endgenerate
 wire payload_fault;
 assign fault=acquisition_fault||payload_fault;
 pt_quad_rx engine(clk,rst_n&&locked,payload_iq,aligned,wire_ready,iq_ready,data,
  wire_count,iq_count,command_valid,payload_fault,opcode,argument);
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin previous<=0;first_seen<=0;rotation<=0;rot_oh<=4'b0001;wait_count<=0;acquisition_fault<=0;locked<=0;end
  else begin
   previous<=in_quad[39:10];
   if(!locked&&!acquisition_fault)begin
    first_seen<=is_first;
    if(|is_second)begin
     locked<=1;
     rotation<=is_second[0]?2'd0:is_second[1]?2'd1:is_second[2]?2'd2:2'd3;
     rot_oh<=is_second[0]?4'b0001:is_second[1]?4'b0010:is_second[2]?4'b0100:4'b1000;
    end else if(&wait_count)acquisition_fault<=1;
    else wait_count<=wait_count+1'b1;
   end
  end
 end
endmodule

// ---------------------------------------------------------------------------
// Rebuild a contiguous quad stream from 0..4 released words per beat.
// Residual words (0..3) are held right-aligned; at most one quad per clock (registered output).
module pt_quad_collect(input wire clk,rst_n,input wire[39:0]data,input wire[2:0]count,
 output reg[39:0]quad,output reg push);
 reg[29:0]res;reg[1:0]rc;
 wire[39:0]keep={{10{count>3'd3}},{10{count>3'd2}},{10{count>3'd1}},{10{count>3'd0}}};
 wire[39:0]incoming=data&keep;
 wire[69:0]merged={30'd0,incoming}<<(10*rc)|{40'd0,res};
 wire[3:0]total={2'd0,rc}+{1'b0,count};
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin res<=0;rc<=0;quad<=0;push<=0;end
  else begin
   push<=total>=4'd4;quad<=merged[39:0];
   if(total>=4'd4)res<=merged[69:40];else res<=merged[29:0];
   rc<=total[1:0];
  end
 end
endmodule
