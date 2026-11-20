// Candidate CDC FIFO. Gray pointers; dual-clock storage needs physical implementation.
// REG_OUT=1 registers the read port (dout = flop) with identical observable behaviour: the
// register reloads mem[next read pointer] on every read-clock edge (rb+1 kept in its own register), and a slot only changes
// while the FIFO is empty at that slot (writer side), so dout equals mem[rb] whenever !empty
// (sim/tb_async_fifo_regout.sv). Used where dout leaves the macro or feeds a deep path.
module pt_async_fifo #(parameter W=10, A=6, REG_OUT=0)(
 input wire wr_clk, rd_clk, rst_n, input wire [W-1:0] din,
 input wire push, pop, output wire [W-1:0] dout,
 output wire full, empty, output wire [A:0] wr_count, rd_count,
 output reg overflow, underflow, output wire wr_active, rd_active);
 (* async_reg="true" *) reg[1:0]wr_reset,rd_reset;
 always @(posedge wr_clk or negedge rst_n)
  if(!rst_n)wr_reset<=0;else wr_reset<={wr_reset[0],1'b1};
 always @(posedge rd_clk or negedge rst_n)
  if(!rst_n)rd_reset<=0;else rd_reset<={rd_reset[0],1'b1};
 wire wr_ready=wr_reset[1],rd_ready=rd_reset[1];
 // Expose the actual storage release; wrappers must not resynchronize it.
 assign wr_active=wr_ready,rd_active=rd_ready;
 reg [W-1:0] mem[0:(1<<A)-1];
 reg [A:0] wb,rb,wg,rg,rg1,rg2,wg1,wg2;
 wire [A:0] wn=wb+1'b1;
 function automatic [A:0] binary(input [A:0] g);
 integer k; begin binary[A]=g[A]; for(k=A-1;k>=0;k=k-1) binary[k]=binary[k+1]^g[k]; end endfunction
 assign full=(wg=={~rg2[A:A-1],rg2[A-2:0]});
 assign empty=(rg==wg2); assign wr_count=wb-binary(rg2);
 assign rd_count=binary(wg2)-rb;
 generate if(REG_OUT)begin:reg_out
  // Two read muxes addressed by registers (rb and rb+1); the late pop only drives the final 2:1.
  reg [W-1:0] dq; reg [A-1:0] rbp1;
  always @(posedge rd_clk or negedge rd_ready) if(!rd_ready) rbp1<=1; else if(pop&&!empty) rbp1<=rbp1+1'b1;
  always @(posedge rd_clk) dq<=(pop&&!empty)?mem[rbp1]:mem[rb[A-1:0]];
  assign dout=dq;
 end else begin:comb_out
  assign dout=mem[rb[A-1:0]];
 end endgenerate
 always @(posedge wr_clk or negedge wr_ready) begin
  if(!wr_ready) begin wb<=0;wg<=0;rg1<=0;rg2<=0;overflow<=0;end
  else begin rg1<=rg;rg2<=rg1;
   if(push) if(!full) begin mem[wb[A-1:0]]<=din;wb<=wn;wg<=(wn>>1)^wn;end else overflow<=1;
  end
 end
 always @(posedge rd_clk or negedge rd_ready) begin
  if(!rd_ready) begin rb<=0;rg<=0;wg1<=0;wg2<=0;underflow<=0;end
  else begin wg1<=wg;wg2<=wg1;
   if(pop) if(!empty) begin rb<=rb+1'b1;rg<=((rb+1'b1)>>1)^(rb+1'b1);end else underflow<=1;
  end
 end
endmodule

module pt_sync_fifo #(parameter W=10,A=5,DEPTH=(1<<A),LOOKAHEAD=0)(input wire clk,rst_n,
 input wire push,pop,input wire[W-1:0]din,output wire[W-1:0]dout,
 output reg full,empty,output reg[A:0]count,output reg overflow,underflow);
 reg[W-1:0]mem[0:DEPTH-1];reg[A-1:0]wp,rp;
 assign dout=mem[rp];
 wire take=pop&&!empty;
 wire put=push&&(!full||(LOOKAHEAD&&take));
 always @(posedge clk or negedge rst_n) begin
  if(!rst_n)begin full<=0;empty<=1;wp<=0;rp<=0;count<=0;overflow<=0;underflow<=0;end
  else begin
   if(put)begin mem[wp]<=din;wp<=wp==DEPTH-1?0:wp+1'b1;end
   if(take)rp<=rp==DEPTH-1?0:rp+1'b1;
   case({put,take})
    2'b10:begin count<=count+1'b1;full<=count==DEPTH-1;empty<=0;end
    2'b01:begin count<=count-1'b1;full<=0;empty<=count==1;end
    default:begin end
   endcase
   if(push&&full&&!(LOOKAHEAD&&take))overflow<=1;if(pop&&empty)underflow<=1;
  end
 end
endmodule

// Disable must flush a streaming domain even when its clock is stopped.
// Release remains synchronized to that clock. Both reset events are explicit
// so a cold reset is modeled even when ENABLE started low before the clock.
module pt_enable_release(input wire clk,rst_n,enable,output wire active);
 (* async_reg="true" *) reg[1:0]release_state;
 wire reset_n=rst_n&&enable;
`ifdef SYNTHESIS
 always @(posedge clk or negedge reset_n)
  if(!reset_n)release_state<=0;
  else release_state<={release_state[0],1'b1};
`elsif FORMAL
 always @(posedge clk or negedge reset_n)
  if(!reset_n)release_state<=0;
  else release_state<={release_state[0],1'b1};
`else
 // The explicit cold-reset event also initializes a simulator whose
 // ENABLE input was already zero before its first clock edge.
 always @(posedge clk or negedge rst_n or negedge enable)
  if(!rst_n||!enable)release_state<=0;
  else release_state<={release_state[0],1'b1};
`endif
 assign active=release_state[1];
endmodule

module pt_sync_bit(input wire clk,rst_n,d,output reg q);
 (* async_reg="true" *) reg meta;
 always @(posedge clk or negedge rst_n)if(!rst_n)begin meta<=0;q<=0;end else begin meta<=d;q<=meta;end
endmodule

// Timing-oriented CDC FIFO for the AC-1 40-bit transport core. Gray
// pointers with two-flop synchronizers as pt_async_fifo, plus:
//  * any even or power-of-two DEPTH: pointers count modulo 2*DEPTH and are
//    Gray-coded with an offset of (2^(A+1)-2*DEPTH)/2, the middle 2*DEPTH codes
//    of the reflected code, whose wrap also changes a single bit;
//  * one-hot write pointer: one AND gate per entry write enable;
//  * registered, conservative counts. rd_count (reader) counts entries whose
//    write pointer was seen up to three reader clocks ago, minus every pop up
//    to this clock: it never over-reports data, and empty uses the same
//    registered pointer, so the count is never negative. ready (writer) is 1
//    only if occupancy before this clock's push, with the read pointer seen up
//    to three writer clocks ago, is at most DEPTH-SPARE: with a one-clock
//    registered producer, SPARE=3 guarantees no overflow (one write in this
//    clock, one in the producer register, one accepted against this ready).
//    full is exact for a power-of-two DEPTH and conservative otherwise; every
//    flag is a compare of registers (no pointer arithmetic before a write
//    enable or a ready register);
//  * registered first-word-fall-through read port (pt_async_fifo REG_OUT=1).
//  * MEMORY (AC-1 sharing S1, MEMORY v3 SPI service; the transport banks are the capture/playback
//    memory, quad indexed). MEMORY=1 (ingress, capture): peek = mem[peek_idx], an SPI-clock
//    (quasi-static) read port; capture itself is the normal write side (the core suppresses pops
//    and stops pushing at full, so entry i holds the i-th captured quad). MEMORY=2 (egress,
//    playback): with play=1 (stopped-only, changes only while ENABLE=0) the array write clock is
//    ~spi_clk through one stopped-only clock mux and spi_we writes spi_d at spi_idx; the read side
//    then ignores the write pointer: entries 0..play_last are sent once (empty after the last) or
//    looped, and rd_count reads DEPTH so the owner's start threshold is met.
module pt_cdc_fifo #(parameter W=40,A=4,DEPTH=(1<<A),SPARE=3,MEMORY=0,POPQ=0,CNTPIPE=0)(
 input wire wr_clk,rd_clk,rst_n,input wire[W-1:0]din,input wire push,pop,
 output wire[W-1:0]dout,output wire full,empty,output wire nonempty,output reg ready,
 output reg[A:0]rd_count,output reg overflow,underflow,output wire wr_active,rd_active,
 output wire[A:0]wr_ptr,rd_ptr,   // binary pointers (write / read domain), modulo 2*DEPTH
 output wire[A:0]rd_ptr_step,output wire rd_take,   // step(rd_ptr) (register) and this clock's read
 input wire[A-1:0]peek_idx,output wire[W-1:0]peek,
 input wire play,play_loop,input wire[A-1:0]play_last,
 input wire spi_clk,spi_we,input wire[A-1:0]spi_idx,input wire[W-1:0]spi_d);
 localparam[A:0]LAST=2*DEPTH-1;
 localparam[A+1:0]SPAN=2*DEPTH;
 localparam[A:0]OFFSET=((1<<(A+1))-2*DEPTH)/2;
 localparam POW2=DEPTH==(1<<A);
 localparam[A:0]FULLC=DEPTH;
 (* async_reg="true" *) reg[1:0]wr_reset,rd_reset;
 always @(posedge wr_clk or negedge rst_n)
  if(!rst_n)wr_reset<=0;else wr_reset<={wr_reset[0],1'b1};
 always @(posedge rd_clk or negedge rst_n)
  if(!rst_n)rd_reset<=0;else rd_reset<={rd_reset[0],1'b1};
 wire wr_ready=wr_reset[1],rd_ready=rd_reset[1];
 assign wr_active=wr_ready,rd_active=rd_ready;
 reg[W-1:0]mem[0:DEPTH-1];
 reg[A:0]wb,rb,wg,wgp,rg,rg1,rg2,wg1,wg2,rbin,rbd,wbin;
 reg[DEPTH-1:0]woh;
 function automatic[A:0]gray(input[A:0]b);
  begin gray=(b+OFFSET)^((b+OFFSET)>>1);end endfunction
 function automatic[A:0]binary(input[A:0]g);
 integer k;reg[A:0]t;begin for(k=A;k>=0;k=k-1)t[k]=^(g>>k);binary=t-OFFSET;end endfunction   // per-bit XOR trees
 function automatic[A:0]step(input[A:0]p);begin step=p==LAST?{(A+1){1'b0}}:p+1'b1;end endfunction
 function automatic[A:0]distance(input[A:0]a,b);   // (a-b) mod 2*DEPTH
 reg[A+1:0]d,e;begin d={1'b0,a}-{1'b0,b};e={1'b0,a}+(SPAN-{1'b0,b});distance=d[A+1]?e[A:0]:d[A:0];end endfunction
 // (the wrapped candidate a + SPAN - b is a parallel adder, not a second adder after the first)
 function automatic[A:0]plus_depth(input[A:0]p);     // (p+DEPTH) mod 2*DEPTH
 reg[A+1:0]d;begin d={1'b0,p}+DEPTH;plus_depth=d>=SPAN?d-SPAN:d;end endfunction
 // rn = step(rb) is a REGISTER (rnr, maintained with rb; timing 2026-11-11: rb -> increment / wrap
 // compare -> distance -> rd_count was the post-synthesis egress_wtx worst path)
 reg[A:0]rnr;
 wire[A:0]wn=step(wb),rn=rnr;
 // full / empty are REGISTERS: the same compares evaluated on next-state values one clock early
 // (both alternatives in parallel, the late put / take only select), so no pointer compare sits
 // between a flop and the 40-bit write-enable / read-select fanout.
 reg full_r,empty_r;
 assign full=full_r;
 reg play_done;
 wire playing=MEMORY==2&&play;
 wire[A-1:0]lastc=play_last>=DEPTH?DEPTH-1:play_last;   // clamp: at most the whole bank
 // playback empty is a REGISTER (pe): asynchronously set while the read side is in reset and loaded
// with the next play_done value, so the reset synchronizer output rd_ready never reaches the
// pop / take / 40-bit read-select logic as data (AC1_R4: egress.rd_active -> empty -> take was the
// -15.6 ns egress_wtx path). Same values as play_done || !rd_ready except one extra empty clock
// right after the read-side reset release (the first pop can only come a clock later).
reg pe;
assign empty=playing?pe:empty_r;
 // POPQ=1 (timing TC9, egress): the caller qualifies pop with `nonempty` (a plain register, = !empty,
 // no playback mux) so take = pop; the caller's pop must never be set while empty.
 reg ne_r;
 assign nonempty=ne_r;
 wire put=push&&!full,take=POPQ?pop:(pop&&!empty);
 wire[A:0]wb_next=put?wn:wb,rb_next=take?rn:rb;
 // next-state compares from registers only, kept as separate nets so the late put / take is a final 2:1
 // Non-power-of-two DEPTH (timing 2026-11-11, ingress_wrx -1.4 ns: wb -> step -> compare with
 // plus_depth(binary(rg2)) -> full): both operands are registers, wnr = step(wb) and rbd = the read
 // pointer + DEPTH registered one writer clock after rg2. rbd lags rg2 by one clock, so full can stay
 // set one writer clock longer after a read (conservative: never an overflow, never a false not-full).
 reg[A:0]wnr;
 // ready (TC9, hcore -2.1 ns mid-PnR: wb/rbin -> distance -> compare -> ready rippled through ~12 levels):
 // occupancy <= DEPTH-SPARE  <=>  wb lies in the window rbin .. rbin+DEPTH-SPARE (mod 2*DEPTH); the window end
 // rlim and its wrap flag are registered with rbin (same rg2 sample), so ready is two compares from registers.
 reg[A:0]rlim;reg rwrap;
 localparam[A+1:0]KREADY=DEPTH-SPARE;
 function automatic[A:0]plus_k(input[A:0]p);
 reg[A+1:0]d;begin d={1'b0,p}+KREADY;plus_k=d>=SPAN?d-SPAN:d;end endfunction
 wire ready_n=rwrap?(wb>=rbin||wb<=rlim):(wb>=rbin&&wb<=rlim);
 (* keep *) wire f_put=POW2?(gray(wn)=={~rg1[A:A-1],rg1[A-2:0]}):(wnr==rbd);
 (* keep *) wire f_hold=POW2?(wg=={~rg1[A:A-1],rg1[A-2:0]}):(wb==rbd);
 // empty compares against wbin (binary(wg2) registered one reader clock later; timing 2026-11-11:
 // wg2 -> Gray decode -> compare -> empty_r was the post-synthesis egress_wtx worst path). The write
 // pointer is seen one clock later: empty stays set one clock longer (conservative, never early).
 (* keep *) wire e_take=rn==wbin,e_hold=rb==wbin;
 wire[A:0]occupancy=distance(wb,rbin);
 (* keep *) wire[A:0]cnt_take=distance(wbin,rn),cnt_hold=distance(wbin,rb);
 // The late put / take select the precomputed alternatives through kept-hierarchy 2:1 muxes:
 // with plain ?: synthesis (opt_share) merged the two compares / subtractors into one behind a
 // pointer mux, putting take back in front of the arithmetic (post-synthesis egress_wtx -1.4 ns).
 wire empty_n,full_n;wire[A:0]cnt_n;
 pt_sel2 #(.W(1)) empty_sel(.s(take),.a(e_hold),.b(e_take),.z(empty_n));
 pt_sel2 #(.W(1)) full_sel(.s(put),.a(f_hold),.b(f_put),.z(full_n));
 pt_sel2 #(.W(A+1)) cnt_sel(.s(take),.a(cnt_hold),.b(cnt_take),.z(cnt_n));
 // Read port (DG9-EG, replaces the three parallel read trees roh / roh1 / roh2): ONE read tree with a
 // registered fetch pointer and a two-entry skid. The tree reads mem[F] (F = foh, one-hot FETCH pointer, a
 // register) into registered half-array partials (pa / pb, split as before); p = pa|pb is the entry fetched
 // one clock earlier. Fetched entries queue in order behind the head: dq (head, = mem[rb] whenever the FIFO
 // reports data) and sk (rb+1); vq / vs / pv mark dq, sk and p valid (vs implies vq, never vs && pv, so at
 // most rb .. rb+2 are in flight). On a take the queue shifts and p lands in the first free slot.
 // F advances (a fetch) when entry F is readable and the queue has room after this clock:
 //   fetch = readable && (take || room),  room = !(vq && (vs || pv)),  readable = playing || (gray(F) != wg2)
 // wg2 is the synchronized write pointer two reader clocks ahead of wbin / empty_r, so an entry is fetched no
 // earlier than the old trees sampled it (written at least one reader clock before), F never passes the write
 // pointer (no stale prefetch), and the head is in dq on the clock empty_r / nonempty clears. room and
 // readable are registers (next-state compares); every pointer / queue next state is computed for take = 0
 // and take = 1 from registers and the late take drives only kept 2:1s (pt_sel2). The playback wrap flag fl
 // ("F is play_last") is a register, so the old roh2 -> play_last 28:1 mux -> roh2 loop (egress_wtx -2.2 /
 // -2.9 ns routed) is gone. Playback: the "is last" flag travels with the data (pl / sl / ql) and drives
 // play_done. On the first clock after the read-side release in playback (pinit) the tree reads the entry
 // after 0 while p already holds entry 0 (sampled during reset), so dq holds entry 0 and p entry 1 when
 // nonempty first rises, as with the old trees. Looped play_last = 0 now sends entry 0 every clock as
 // specified (the old roh1 reset value skipped the wrap and sent 0, 1, .., DEPTH-1 first).
 // dout while the FIFO reports no data: the last head or a fetched entry (old: mem[rb], a stale slot or a word
 // being written); every consumer qualifies dout with nonempty / empty / rd_count.
 // Equivalence against the three-tree read side: sim/tb_cdc_fifo_readside_equiv.sv.
 reg[W-1:0]dq,sk;reg[DEPTH-1:0]foh;reg[A:0]fbn,fg;reg fl,vq,vs,pv,ql,sl,pl,rinit;
 wire last0=lastc==0,last1=lastc==1;
 wire[DEPTH-1:0]lastm1=(last0?{DEPTH{1'b0}}:({{(DEPTH-1){1'b0}},1'b1}<<(lastc-1'b1)));   // one-hot play_last-1
 // pinit = the first clock after the read-side release, in playback. rd_rel is a low-fanout replica of the
 // second synchronizer stage rd_reset[1] (same D rd_reset[0], clock and reset rst_n; kept-hierarchy so synthesis
 // does not merge it), so the release reset tree never reaches the read-tree address.
 wire rd_rel;
 pt_dff_rep rd_rel_rep(rd_clk,rst_n,rd_reset[0],rd_rel);
 wire pinit=playing&&rinit&&rd_rel;
 // readable / room are registers holding (F's Gray != wg2) and !(vq && (vs || pv)) (next-state compares below)
 reg rdr,room;
 wire readable=playing||rdr;
 wire pvx=pv||pinit;
 wire[DEPTH-1:0]fstep=(playing&&fl)?{{(DEPTH-1){1'b0}},1'b1}:{foh[DEPTH-2:0],foh[DEPTH-1]};
 wire fl_step=playing&&(fl?last0:|(foh&lastm1));
 // pinit: address the entry after 0 (0 itself if play_last is 0); afterwards F. F is entry 0 (its reset value)
 // during pinit, so only address bits 0 and 1 take the pinit term.
 wire pin1=pinit&&!last0;
 wire[DEPTH-1:0]faddr={foh[DEPTH-1:2],foh[1]||pin1,foh[0]&&!pin1};
 wire ftag=pinit?(last0||last1):rinit?last0:fl;
 // F after the pinit clock: two entries past 0 with the playback wrap
 wire[DEPTH-1:0]finit=(last0||last1)?{{(DEPTH-1){1'b0}},1'b1}:{{(DEPTH-3){1'b0}},3'b100};
 wire flinit=last0||(!last1&&lastc==2);
 initial if(DEPTH<3)$fatal(1,"pt_cdc_fifo: DEPTH must be at least 3 (one-tree read side)");
 // Next control state for take = 0 (h) and take = 1 (t), both from registers; the late take only drives kept 2:1s.
 localparam CS=DEPTH+2*(A+1)+6;
 wire fetch_t=readable,fetch_h=readable&&room;   // room is 1 while vq is 0 (pinit)
 // the two fetch alternatives of every pointer register (fetch = 1: advance) are plain wires of registers
 wire[DEPTH-1:0]o_adv=pinit?finit:fstep,o_hold=pinit?finit:foh;
 wire l_adv=pinit?flinit:fl_step,l_hold=pinit?flinit:fl;
 wire[A:0]bn_adv=step(fbn),g_adv=gray(fbn);
 wire[CS-1:0]cs_h={fetch_h?o_adv:o_hold,fetch_h?l_adv:l_hold,fetch_h?bn_adv:fbn,fetch_h?g_adv:fg,
  vq||pvx,vq&&(vs||pvx),fetch_h,(fetch_h?g_adv:fg)!=wg1,!((vq||pvx)&&(vq&&(vs||pvx)||fetch_h))};   // wg2 <= wg1 now
 wire[CS-1:0]cs_t={fetch_t?o_adv:o_hold,fetch_t?l_adv:l_hold,fetch_t?bn_adv:fbn,fetch_t?g_adv:fg,
  vs||pvx,vs&&pvx,fetch_t,(fetch_t?g_adv:fg)!=wg1,!((vs||pvx)&&(vs&&pvx||fetch_t))};
 wire[CS-1:0]cs_n;
 pt_sel2 #(.W(CS)) cs_sel(.s(take),.a(cs_h),.b(cs_t),.z(cs_n));
 always @(posedge rd_clk or negedge rd_ready)
  if(!rd_ready)begin foh<=1;fl<=1'b0;fbn<=step(0);fg<=gray(0);vq<=1'b0;vs<=1'b0;pv<=1'b0;rdr<=1'b0;room<=1'b1;rinit<=1'b1;end
  else begin rinit<=1'b0;{foh,fl,fbn,fg,vq,vs,pv,rdr,room}<=cs_n;end
 // playback: entries 0..play_last (the head's last flag), then stop or wrap
 wire play_done_n=play_done||(playing&&take&&ql&&!play_loop);
 always @(posedge rd_clk or negedge rd_ready)
  if(!rd_ready)begin play_done<=0;pe<=1;end
  else begin play_done<=play_done_n;pe<=play_done_n;end
 always @(posedge rd_clk or negedge rd_ready)
  if(!rd_ready)ne_r<=1'b0;else ne_r<=!(playing?play_done_n:empty_n);
 localparam HALF=(DEPTH+1)/2;
 reg[W-1:0]ca,cb;integer j;
 always @*begin
  ca=0;cb=0;
  for(j=0;j<DEPTH;j=j+1)
   if(j<HALF)ca=ca|({W{faddr[j]}}&mem[j]);else cb=cb|({W{faddr[j]}}&mem[j]);
 end
 reg[W-1:0]pa,pb;
 always @(posedge rd_clk)begin pa<=ca;pb<=cb;pl<=ftag;end
 wire[W-1:0]p=pa|pb;
 // data moves: registers select the candidates, the late take drives only the final kept 2:1s
 wire[W-1:0]dq_hold=vq?dq:p,dq_take=vs?sk:p,sk_hold=vs?sk:p;wire[W-1:0]dq_n,sk_n;
 pt_sel2 #(.W(W)) dq_sel(.s(take),.a(dq_hold),.b(dq_take),.z(dq_n));
 pt_sel2 #(.W(W)) sk_sel(.s(take),.a(sk_hold),.b(p),.z(sk_n));
 wire ql_n,sl_n;
 pt_sel2 #(.W(2)) tag_sel(.s(take),.a({vq?ql:pl,vs?sl:pl}),.b({vs?sl:pl,pl}),.z({ql_n,sl_n}));
 always @(posedge rd_clk)begin
  dq<=dq_n;sk<=sk_n;
  ql<=ql_n;sl<=sl_n;
 end
`ifdef FORMAL
 always @(posedge rd_clk)if(rd_ready)begin
  assert(!(vs&&!vq));assert(!(vs&&pv));assert(!(take&&!vq));
  assert(!(!vq&&!take&&vs));
  assert(rdr==(fg!=wg2));assert(room==!(vq&&(vs||pv)));
 end
`endif
 assign dout=dq;
 assign wr_ptr=wb,rd_ptr=rb,rd_ptr_step=rnr,rd_take=take;
 // CNTPIPE=1 (TC11, egress_wtx: rnr -> 6-bit distance ripple -> rd_count was -0.43 ns at 12.3 ns): rd_count is
 // distance(wbin, rb) of the PREVIOUS clock in two stages: stage 1 registers the 3-bit low difference with its
 // borrow and the four high-part candidates (borrow 0/1, wrapped +SPAN/8 or not; SPAN is a multiple of 8),
 // stage 2 only selects. The count is distance(wbin, rb) one clock old: it lags the writer (under-count) but
 // can miss the last two takes (over-count by <= 2); consumers that pop before a start threshold add 2.
 reg[2:0]cp_lo;reg cp_lob;reg[A-2:0]cp_h0,cp_h1,cp_h0w,cp_h1w;reg cp_n0,cp_n1;
 wire[3:0]cp_lo4={1'b0,wbin[2:0]}-{1'b0,rb[2:0]};
 wire[A-2:0]cp_ah=wbin[A:3],cp_bh=rb[A:3];
 wire[A-1:0]cp_d0={1'b0,cp_ah}-{1'b0,cp_bh},cp_d1=cp_d0-1'b1;
 localparam[A-2:0]SPAN8=SPAN/8;
 wire[A-2:0]cp_sel=cp_lob?(cp_n1?cp_h1w:cp_h1):(cp_n0?cp_h0w:cp_h0);
 wire[A:0]cp_count={cp_sel,cp_lo};
 always @(posedge rd_clk or negedge rd_ready)
  if(!rd_ready)begin cp_lo<=0;cp_lob<=0;cp_h0<=0;cp_h1<=0;cp_h0w<=0;cp_h1w<=0;cp_n0<=0;cp_n1<=0;end
  else begin
   cp_lo<=cp_lo4[2:0];cp_lob<=cp_lo4[3];
   cp_h0<=cp_d0[A-2:0];cp_h1<=cp_d1[A-2:0];cp_n0<=cp_d0[A-1];cp_n1<=cp_d1[A-1];
   cp_h0w<=cp_d0[A-2:0]+SPAN8;cp_h1w<=cp_d1[A-2:0]+SPAN8;
  end
 initial if(CNTPIPE&&(SPAN%8)!=0)$fatal(1,"CNTPIPE needs 2*DEPTH to be a multiple of 8");
 integer i;
 // Write port pipelined (timing closure 2026-11-11): the per-entry write enables are REGISTERS
 // (we_r = put & one-hot pointer, one flop per entry) and the data is registered with them, so the
 // late push/full decision drives DEPTH flops instead of the DEPTH x W array enables (AC1_R4:
 // lane_in_valid -> 1,120 ingress flops, -7.7 ns). The array is written one clock after the push;
 // the Gray write pointer seen by the reader (wgp) is published one clock later to match.
 reg[DEPTH-1:0]we_r;reg[W-1:0]din_r;
 always @(posedge wr_clk or negedge wr_ready)
  if(!wr_ready)we_r<=0;else we_r<=put?woh:{DEPTH{1'b0}};
 always @(posedge wr_clk)din_r<=din;
 generate if(MEMORY==2)begin:spi_port
  // one stopped-only clock mux on the array write clock (SPI writes land on the SCLK fall)
  wire mem_clk;
  pt_clock_mux memory_clock_mux(.I0(wr_clk),.I1(~spi_clk),.S(play),.Z(mem_clk));
  always @(posedge mem_clk)
   for(i=0;i<DEPTH;i=i+1)
    if(play?(spi_we&&spi_idx==i):we_r[i])mem[i]<=play?spi_d:din_r;
  assign peek={W{1'b0}};
 end else begin:wr_port
  always @(posedge wr_clk)
   for(i=0;i<DEPTH;i=i+1)if(we_r[i])mem[i]<=din_r;
  if(MEMORY==1)begin:peek_port assign peek=mem[peek_idx];end
  else begin:no_peek assign peek={W{1'b0}};end
 end endgenerate
 always @(posedge wr_clk or negedge wr_ready)begin
  if(!wr_ready)begin wb<=0;wnr<=1;wg<=gray(0);wgp<=gray(0);rg1<=gray(0);rg2<=gray(0);rbin<=0;rbd<=DEPTH;rlim<=KREADY;rwrap<=1'b0;woh<=1;overflow<=0;ready<=0;full_r<=0;end
  else begin
   full_r<=full_n;
   wgp<=wg;   // published after the array write (we_r) lands
   rg1<=rg;rg2<=rg1;rbin<=binary(rg2);rbd<=plus_depth(binary(rg2));
   rlim<=plus_k(binary(rg2));rwrap<=binary(rg2)>=SPAN-KREADY;
   ready<=ready_n;   // == (occupancy <= DEPTH-SPARE)
`ifdef FORMAL
   assert(ready_n==(occupancy<=DEPTH-SPARE));
`endif
   if(put)begin wb<=wn;wnr<=step(wn);wg<=gray(wn);woh<={woh[DEPTH-2:0],woh[DEPTH-1]};end
   if(push&&full)overflow<=1;
  end
 end
 always @(posedge rd_clk or negedge rd_ready)begin
  if(!rd_ready)begin rb<=0;rnr<=step(0);rg<=gray(0);wg1<=gray(0);wg2<=gray(0);wbin<=0;rd_count<=0;underflow<=0;empty_r<=1;end
  else begin
   empty_r<=empty_n;
   wg1<=wgp;wg2<=wg1;wbin<=binary(wg2);
   if(!CNTPIPE)rd_count<=playing?FULLC:cnt_n;   // both alternatives from registers; `take` selects late (pt_sel2)
   else rd_count<=playing?FULLC:cp_count;
   if(take)begin rb<=rn;rnr<=step(rn);rg<=gray(rn);end
   if(pop&&empty)underflow<=1;
  end
 end
endmodule

// Replicated reset-release flop (kept): async assert, release on the first clock edge after rst_n.
`ifndef FORMAL
(* keep_hierarchy = "yes" *)
`endif
module pt_rst_rep(input wire clk, rst_n, output reg q);
    always @(posedge clk or negedge rst_n) if (!rst_n) q <= 1'b0; else q <= 1'b1;
endmodule

// Replicated flop (kept): a copy of another flop with the same D, clock and reset that synthesis must not merge.
`ifndef FORMAL
(* keep_hierarchy = "yes" *)
`endif
module pt_dff_rep(input wire clk, rst_n, d, output reg q);
    always @(posedge clk or negedge rst_n) if (!rst_n) q <= 1'b0; else q <= d;
endmodule

// Kept 2:1 select (z = s ? b : a): a hierarchy boundary so synthesis cannot share the logic in front
// of the two inputs into one operator behind a select (late-select timing structure).
`ifndef FORMAL
(* keep_hierarchy = "yes" *)
`endif
module pt_sel1(input wire s, a, b, output wire z);
 assign z = s ? b : a;
endmodule
// W-bit wrapper (flattened) of kept 1-bit selects: a parameterized kept module would survive
// synthesis as a $paramod instance, which the flow counts as an unmapped cell.
module pt_sel2 #(parameter integer W=1)(input wire s, input wire [W-1:0] a, b, output wire [W-1:0] z);
 genvar i;
 generate for (i = 0; i < W; i = i + 1) begin : b_
  pt_sel1 m(.s(s), .a(a[i]), .b(b[i]), .z(z[i]));
 end endgenerate
endmodule
