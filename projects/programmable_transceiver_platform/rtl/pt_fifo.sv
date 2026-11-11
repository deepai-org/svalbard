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
module pt_cdc_fifo #(parameter W=40,A=4,DEPTH=(1<<A),SPARE=3,MEMORY=0)(
 input wire wr_clk,rd_clk,rst_n,input wire[W-1:0]din,input wire push,pop,
 output wire[W-1:0]dout,output wire full,empty,output reg ready,
 output reg[A:0]rd_count,output reg overflow,underflow,output wire wr_active,rd_active,
 output wire[A:0]wr_ptr,rd_ptr,   // binary pointers (write / read domain), modulo 2*DEPTH
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
 integer k;reg[A:0]t;begin t[A]=g[A];for(k=A-1;k>=0;k=k-1)t[k]=t[k+1]^g[k];binary=t-OFFSET;end endfunction
 function automatic[A:0]step(input[A:0]p);begin step=p==LAST?{(A+1){1'b0}}:p+1'b1;end endfunction
 function automatic[A:0]distance(input[A:0]a,b);   // (a-b) mod 2*DEPTH
 reg[A+1:0]d;begin d={1'b0,a}-{1'b0,b};distance=d[A+1]?d+SPAN:d;end endfunction
 function automatic[A:0]plus_depth(input[A:0]p);     // (p+DEPTH) mod 2*DEPTH
 reg[A+1:0]d;begin d={1'b0,p}+DEPTH;plus_depth=d>=SPAN?d-SPAN:d;end endfunction
 wire[A:0]wn=step(wb),rn=step(rb);
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
 wire put=push&&!full,take=pop&&!empty;
 wire[A:0]wb_next=put?wn:wb,rb_next=take?rn:rb;
 // next-state compares from registers only, kept as separate nets so the late put / take is a final 2:1
 (* keep *) wire f_put=POW2?(gray(wn)=={~rg1[A:A-1],rg1[A-2:0]}):(wn==plus_depth(binary(rg2)));
 (* keep *) wire f_hold=POW2?(wg=={~rg1[A:A-1],rg1[A-2:0]}):(wb==plus_depth(binary(rg2)));
 (* keep *) wire e_take=rn==binary(wg2),e_hold=rb==binary(wg2);
 wire[A:0]occupancy=distance(wb,rbin);
 // Read port: registered ONE-HOT entry selects (head and head+1) drive two AND-OR trees straight
 // from flops (no decode before the 40-bit fanout); the late `take` only drives the final 2:1.
 reg[W-1:0]dq;reg[DEPTH-1:0]roh,roh1;
 always @(posedge rd_clk or negedge rd_ready)
  if(!rd_ready)begin roh<=1;roh1<=2;end
  else if(take)begin roh<=roh1;
   roh1<=(playing&&roh1[lastc])?{{(DEPTH-1){1'b0}},1'b1}:{roh1[DEPTH-2:0],roh1[DEPTH-1]};end
 // playback: entries 0..play_last (one-hot head reaches play_last), then stop or wrap
 wire play_done_n=play_done||(playing&&take&&roh[lastc]&&!play_loop);
 always @(posedge rd_clk or negedge rd_ready)
  if(!rd_ready)begin play_done<=0;pe<=1;end
  else begin play_done<=play_done_n;pe<=play_done_n;end
 reg[W-1:0]sel0,sel1;integer j;
 always @*begin sel0=0;sel1=0;
  for(j=0;j<DEPTH;j=j+1)begin sel0=sel0|({W{roh[j]}}&mem[j]);sel1=sel1|({W{roh1[j]}}&mem[j]);end end
 always @(posedge rd_clk)dq<=take?sel1:sel0;
 assign dout=dq;
 assign wr_ptr=wb,rd_ptr=rb;
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
  if(!wr_ready)begin wb<=0;wg<=gray(0);wgp<=gray(0);rg1<=gray(0);rg2<=gray(0);rbin<=0;rbd<=DEPTH;woh<=1;overflow<=0;ready<=0;full_r<=0;end
  else begin
   full_r<=put?f_put:f_hold;
   wgp<=wg;   // published after the array write (we_r) lands
   rg1<=rg;rg2<=rg1;rbin<=binary(rg2);rbd<=plus_depth(binary(rg2));
   ready<=occupancy<=DEPTH-SPARE;
   if(put)begin wb<=wn;wg<=gray(wn);woh<={woh[DEPTH-2:0],woh[DEPTH-1]};end
   if(push&&full)overflow<=1;
  end
 end
 always @(posedge rd_clk or negedge rd_ready)begin
  if(!rd_ready)begin rb<=0;rg<=gray(0);wg1<=gray(0);wg2<=gray(0);wbin<=0;rd_count<=0;underflow<=0;empty_r<=1;end
  else begin
   empty_r<=take?e_take:e_hold;
   wg1<=wgp;wg2<=wg1;wbin<=binary(wg2);
   rd_count<=playing?FULLC:take?distance(wbin,rn):distance(wbin,rb);   // both from registers; `take` selects late
   if(take)begin rb<=rn;rg<=gray(rn);end
   if(pop&&empty)underflow<=1;
  end
 end
endmodule
