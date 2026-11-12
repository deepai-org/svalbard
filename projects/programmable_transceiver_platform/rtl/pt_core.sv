// Exclusive streaming transport core, AC-1: 40-bit quads (four ten-bit host
// words) on core_clk = host word clock / 4 (78.125 MHz at 2.5 Gb/s line/8).
// The pad-edge DDR registers and the 1:4 / 4:1 gearboxes are in
// pt_host_link; this core sees one H2D quad and launches one D2H quad per
// core clock. Wired boundary: 40-bit quads per wire_rx_clk / wire_tx_clk
// (line/40, 62.5 MHz at 2.5 Gb/s), word 0 (earliest on the line) in [9:0].
// RF boundary: one 24-bit sample per rf_rx_clk / rf_tx_clk edge. Samples are
// packed into / unpacked from quads in the sample-clock domains, so every CDC
// FIFO carries quads and 40 MS/s service also runs at the reduced host rate
// (div2, core clock 39.06 MHz) that RF modes use.
// Stopped-only payload_iq selects the sole owner of the shared storage.
// Stopped-only linecode (IX-2) inserts the 8b/10b offload (rtl/pt_linecode.sv) at the wired boundary:
// the host then carries decoded 9-bit symbols, 0.9 x line rate.
// Fast gain (opcode4, RXR-D2, RF ownership): an accepted H2D gain command is applied in the RF RX
// sample domain (rx_gain/rx_gain_active drive the LNA/PGA controls in pt_digital_macro), which at the
// same clock discards the packing reservoir and then the next SETTLE samples (pt_gain_rx), restarts
// packing at a quad boundary and reports the boundary to the D2H engine, which completes the older
// samples and then sends the opcode4 gain-status frame with the discarded-pair count.
module pt_core #(parameter WIRE_IN_A=5,WIRE_IN_DEPTH=28,EGRESS_A=5,EGRESS_DEPTH=24,WIRE_START=8,RF_START=5,
 GAIN_SETTLE=20)(
 input wire rst_n,enable,mode8,
 input wire host_clk,wire_rx_clk,wire_tx_clk,rf_rx_clk,rf_tx_clk,
 input wire[39:0]h2d_quad,output wire[39:0]d2h_quad,
 input wire[39:0]wire_rx_data,input wire wire_rx_valid,
 output wire[39:0]wire_tx_data,output wire wire_tx_valid,input wire wire_tx_request,
 input wire[23:0]rf_rx_sample,input wire rf_rx_valid,
 output wire[23:0]rf_tx_sample,output wire rf_tx_valid,input wire rf_tx_request,
 output wire[15:0]status,output wire wire_idle,rf_mute,input wire payload_iq,
 input wire linecode,
 output wire[6:0]rx_gain,output wire rx_gain_active,   // rf_rx_clk domain
 // MEMORY v3 (sharing S1): capture into the ingress bank, playback from the egress bank. Levels are
 // stopped-only (regfile accepts 0x23 only while ENABLE=0); SPI port on spi_clk (writes on its fall).
 input wire mem_capture,mem_play,mem_loop,input wire[4:0]mem_last,
 input wire spi_clk,mem_we,input wire[4:0]mem_idx,input wire[39:0]mem_wdata,
 output wire[39:0]mem_rdata,output reg capture_done,
 // Shared wired pattern lane (plan step 4): with pat_sel (stopped-only debug level) the pattern
 // generator's word (wire_tx_clk register) goes out through the same wire_low (falling) /
 // wire_high (rising) launch registers as payload, instead of straight from rising-edge flops.
 input wire pat_sel,input wire[39:0]pat_word,
 // Wired output stage handshake (timing 2026-11-11): pat_valid / pat_idle are the pattern source's
 // valid / idle; wire_req_int = the stage's load (!wire_tx_valid || wire_tx_request) is the request
 // the sources see (the pattern generator steps on wire_req_int && its valid).
 input wire pat_valid,pat_idle,output wire wire_req_int);
 wire eh,ewr,ewt,err,ert;
 pt_enable_release e0(host_clk,rst_n,enable,eh);
 pt_sync_bit e2(wire_rx_clk,rst_n,enable,ewr);pt_sync_bit e3(wire_tx_clk,rst_n,enable,ewt);
 // The RF pack/unpack reservoirs sit in the sample-clock domains: disable must
 // flush them even while those clocks are stopped (owner change lifecycle).
 pt_enable_release e4(rf_rx_clk,rst_n,enable,err);pt_enable_release e5(rf_tx_clk,rst_n,enable,ert);
 wire crst=rst_n&&eh;
 // Timing closure 2026-11-11: the hcore engines take their reset from replicated local release flops
 // (all sample 1 on the first host_clk edge after crst deasserts, so they release on the same edge);
 // the core_rst_n -> thousands-of-RN recovery tree becomes four local trees.
 wire crst_tx,crst_rx,crst_col,crst_gm;
 pt_rst_rep rr_tx(host_clk,crst,crst_tx);pt_rst_rep rr_rx(host_clk,crst,crst_rx);
 pt_rst_rep rr_col(host_clk,crst,crst_col);pt_rst_rep rr_gm(host_clk,crst,crst_gm);
 // Bank reset: in memory mode (SPI-only fallback, possibly no host clock) the banks release from
 // ENABLE itself; each bank re-synchronizes its release per side (pt_cdc_fifo wr_reset/rd_reset).
 wire mem_mode=mem_capture||mem_play;
 wire frst=rst_n&&(mem_mode?enable:eh);
 reg wire_running,wire_starved,rf_running,rf_starved;
 // ---------------- D2H sources. Exclusive ownership permits one ingress bank,
 // as for egress: its write clock is the stopped-selected owner's input clock
 // (wired quad clock, or the RF sample clock with samples packed into quads
 // next to the converter). Disable holds both FIFO domains in reset even with
 // stopped clocks; changing owners requires disable and a flush.
 wire ingress_clk;
 pt_clock_mux ingress_clock_mux(.I0(wire_rx_clk),.I1(rf_rx_clk),.S(payload_iq),.Z(ingress_clk));
 wire[39:0]rf_quad;wire rf_quad_push;
 wire gain_flush,gain_drop;wire[3:0]pack_base;
 pt_sample_pack packer(rf_rx_clk,rst_n&&err,mode8,
  mode8?{8'd0,rf_rx_sample[23:16],rf_rx_sample[11:4]}:rf_rx_sample,rf_rx_valid&&payload_iq&&!gain_drop,rf_quad,rf_quad_push,
  gain_flush,pack_base);
 // IX-2 8b/10b receive offload (wire_rx_clk)
 wire[39:0]lc_rx_quad;wire lc_rx_valid,lc_aligned,lc_code_error;
 pt_lc_rx lc_rx(.clk(wire_rx_clk),.rst_n(rst_n),.en(linecode&&ewr&&!payload_iq),.din(wire_rx_data),.din_valid(wire_rx_valid),
  .dout(lc_rx_quad),.dout_valid(lc_rx_valid),.aligned(lc_aligned),.code_error(lc_code_error));
 // ---------------- INGRESS LANE BOUNDARY (the only owner-specific seam on the D2H side): the lane
 // adapters (wired raw | 8b/10b RX | radio sample pack) feed one registered 40-bit lane on the
 // stopped-only owner clock; everything after it is shared. The register also isolates the
 // adapter mux from the bank write-enable fanout.
 reg[39:0]lane_in;reg lane_in_valid;
 always @(posedge ingress_clk or negedge rst_n)
  if(!rst_n)begin lane_in<=0;lane_in_valid<=0;end
  else begin
   lane_in<=payload_iq?rf_quad:linecode?lc_rx_quad:wire_rx_data;
   lane_in_valid<=payload_iq?(rf_quad_push&&err):linecode?lc_rx_valid:(wire_rx_valid&&ewr);
  end
 // capture: the bank fills from the lane (no host pops) and stops at full; done is a raw level
 wire in_full;
 always @(posedge ingress_clk or negedge rst_n)
  if(!rst_n)capture_done<=0;else capture_done<=mem_capture&&(payload_iq?err:ewr)&&in_full;
 wire[39:0]in_head;wire[WIRE_IN_A:0]in_quads_raw,in_wr_ptr,in_rd_ptr,in_rd_step;wire in_rd_take;wire wr_pop,iq_pop,in_ov,in_un;
 wire[39:0]mem_peek;   // declared before use (strict elaboration, container iverilog)
 pt_cdc_fifo #(.W(40),.A(WIRE_IN_A),.DEPTH(WIRE_IN_DEPTH),.MEMORY(1)) ingress(
  .wr_clk(ingress_clk),.rd_clk(host_clk),.rst_n(frst),
  .din(lane_in),.push(lane_in_valid&&!(mem_capture&&in_full)),.pop((wr_pop||iq_pop)&&!mem_capture),
  .dout(in_head),.full(in_full),.empty(),.ready(),.rd_count(in_quads_raw),
  .overflow(in_ov),.underflow(in_un),.wr_active(),.rd_active(),.wr_ptr(in_wr_ptr),.rd_ptr(in_rd_ptr),
  .rd_ptr_step(in_rd_step),.rd_take(in_rd_take),
  .peek_idx(mem_idx),.peek(mem_peek),.play(1'b0),.play_loop(1'b0),.play_last(5'd0),
  .spi_clk(1'b0),.spi_we(1'b0),.spi_idx(5'd0),.spi_d(40'd0));
 // capture readback is 0 until the capture is complete (legacy MEMORY semantics; no array X/garbage)
 assign mem_rdata=capture_done?mem_peek:40'd0;
 wire[WIRE_IN_A:0]in_quads=mem_capture?{(WIRE_IN_A+1){1'b0}}:in_quads_raw;   // capture: host engine idles
 // ---------------- fast gain: commit (hcore), apply/discard/mark (rf_rx), report (hcore)
 reg gain_toggle,gain_pending,gain_rejected;reg[6:0]gain_arg;
 wire gain_commit,gain_echo;
 wire[6:0]gain_gap;wire[WIRE_IN_A:0]mark_ptr;wire mark_toggle;
 pt_gain_rx #(.A(WIRE_IN_A),.SETTLE(GAIN_SETTLE)) gain_rx(.clk(rf_rx_clk),.rst_n(rst_n&&err),.toggle(gain_toggle),
  .gain_h(gain_arg),.mode8(mode8),.base(pack_base),.valid(rf_rx_valid&&payload_iq),.wr_ptr(in_wr_ptr),
  .flush(gain_flush),.drop(gain_drop),.gain(rx_gain),.active(rx_gain_active),.gap(gain_gap),
  .mark_ptr(mark_ptr),.mark_toggle(mark_toggle));
 wire mark_sync;reg mark_ack;
 pt_sync_bit gm(host_clk,crst_gm,mark_toggle,mark_sync);
 wire mk_seen=mark_sync!=mark_ack;
 // complete older quads still in the FIFO: (mark_ptr - rd_ptr) mod 2*DEPTH. Timing 2026-11-11 (hcore,
 // in_rd_ptr -> subtract -> wrap -> frame_tx before_r): a REGISTER holding the distance to the read
 // pointer this FIFO read side will have after this clock (both candidates from registers, the
 // late take selects), i.e. the same value as the combinational distance one clock later. mark_ptr
 // (rf_rx domain) is stable long before mk_seen (two-flop synchronized toggle) makes it count.
 function automatic[WIRE_IN_A:0]in_dist(input[WIRE_IN_A:0]a,b);
  reg[WIRE_IN_A+1:0]d,e;begin d={1'b0,a}-{1'b0,b};e={1'b0,a}+(2*WIRE_IN_DEPTH-{1'b0,b});
  in_dist=d[WIRE_IN_A+1]?e[WIRE_IN_A:0]:d[WIRE_IN_A:0];end endfunction
 wire[WIRE_IN_A:0]pre_take=in_dist(mark_ptr,in_rd_step),pre_hold=in_dist(mark_ptr,in_rd_ptr);wire[WIRE_IN_A:0]pre_n;
 pt_sel2 #(.W(WIRE_IN_A+1)) pre_sel(.s(in_rd_take),.a(pre_hold),.b(pre_take),.z(pre_n));
 reg[WIRE_IN_A:0]pre_quads;
 always @(posedge host_clk or negedge crst_tx)if(!crst_tx)pre_quads<=0;else pre_quads<=pre_n;
 wire wr_ov=!payload_iq&&in_ov,wr_un=!payload_iq&&in_un,rf_ov=payload_iq&&in_ov,rf_un=payload_iq&&in_un;
 pt_quad_link_tx #(.CW(WIRE_IN_A)) frame_tx(host_clk,crst_tx,payload_iq,in_head,in_head,in_quads,in_quads,
  4'd0,8'd0,wr_pop,iq_pop,d2h_quad,gain_commit,gain_arg,mk_seen,pre_quads,gain_gap,gain_echo);
 // ---------------- H2D
 wire[39:0]received;wire[2:0]wire_words,iq_words;
 wire wire_ready,iq_ready,command_valid,rx_fault,locked;
 wire[3:0]opcode;wire[7:0]argument;
 pt_quad_link_rx frame_rx(host_clk,crst_rx,payload_iq,h2d_quad,wire_ready,iq_ready,
  received,wire_words,iq_words,command_valid,rx_fault,locked,opcode,argument);
 // One collector serves the exclusive owner (the inactive count is zero).
 wire[39:0]rx_quad;wire rx_push;
 pt_quad_collect collect(host_clk,crst_col,received,wire_words|iq_words,rx_quad,rx_push);
 // Exclusive ownership permits one storage bank. Owner changes occur only
 // while disabled; asynchronous disable holds both FIFO domains reset even
 // if the core clock has stopped before the selected output clock changes.
 wire egress_clk;
 pt_clock_mux egress_clock_mux(.I0(wire_tx_clk),.I1(rf_tx_clk),.S(payload_iq),.Z(egress_clk));
 wire[39:0]egress_head;wire[EGRESS_A:0]egress_count;wire egress_full,egress_empty,egress_ov,egress_un,egress_ready;
 wire rf_unpack_ready;
 wire lc_pop,lc_qv;wire[39:0]lc_q;
 wire wreq,wire_load;   // stream consumer request behind the wired output stage (declared before use)
 // Egress pop decode (timing TC9, egress_wtx: empty -> owner muxes -> pop -> take was the worst path):
 // the stopped-only owner selects, pat_sel and the wired start state are folded into per-owner gate
 // REGISTERS, and the FIFO's `nonempty` is a plain register (POPQ=1: take = pop), so take is one
 // AND-OR of registers and the late requests: rf_unpack_ready (register), lc_pop, wire_load.
 // eg_w = the next value of (wired owner && !pat_sel && wire_running); the owner / pat_sel bits are seen
 // one clock later (they change only while stopped). Same pops as the former owner mux otherwise.
 wire egress_ne;reg eg_r,eg_l,eg_w;wire wire_running_n;
 wire eg_rst_n=rst_n&&enable;
 always @(posedge rf_tx_clk or negedge eg_rst_n)if(!eg_rst_n)eg_r<=1'b0;else eg_r<=payload_iq;
 always @(posedge wire_tx_clk or negedge eg_rst_n)
  if(!eg_rst_n)begin eg_l<=1'b0;eg_w<=1'b0;end
  else begin eg_l<=!payload_iq&&linecode;eg_w<=!payload_iq&&!linecode&&!pat_sel&&wire_running_n;end
 // The gates clear ASYNCHRONOUSLY on disable (rst_n && enable; owner / linecode / pat_sel change only while
 // disabled), so a gate whose TX clock has stopped cannot stay set across an owner change (independent
 // review: eg_r stale after rf_tx_clk stops and the owner switches to wired).
 wire egress_pop=(rf_unpack_ready&&eg_r&&egress_ne)||(lc_pop&&eg_l)||(wire_load&&eg_w&&egress_ne);
 // Review TC12 assertion (simulation): the owner / linecode / pattern selects that the eg_* gates hold
 // may change only while the egress is disabled (eg_rst_n low). Checked in both TX clock domains: across
 // two consecutive edges with eg_rst_n high throughout, {payload_iq, linecode, pat_sel} must be equal.
`ifndef SYNTHESIS
`ifndef FORMAL
 reg[2:0]a_sel_w,a_sel_r;reg a_w_ok,a_r_ok;
 always @(posedge wire_tx_clk or negedge eg_rst_n)
  if(eg_rst_n!==1'b1||^{payload_iq,linecode,pat_sel}===1'bx)a_w_ok<=1'b0;   // armed only while enabled with known selects
  else begin
   if(a_w_ok&&a_sel_w!=={payload_iq,linecode,pat_sel})
    $fatal(1,"pt_core: payload_iq/linecode/pat_sel changed while enabled (wire_tx_clk): %b -> %b",a_sel_w,{payload_iq,linecode,pat_sel});
   a_sel_w<={payload_iq,linecode,pat_sel};a_w_ok<=1'b1;
  end
 always @(posedge rf_tx_clk or negedge eg_rst_n)
  if(eg_rst_n!==1'b1||^{payload_iq,linecode,pat_sel}===1'bx)a_r_ok<=1'b0;   // armed only while enabled with known selects
  else begin
   if(a_r_ok&&a_sel_r!=={payload_iq,linecode,pat_sel})
    $fatal(1,"pt_core: payload_iq/linecode/pat_sel changed while enabled (rf_tx_clk): %b -> %b",a_sel_r,{payload_iq,linecode,pat_sel});
   a_sel_r<={payload_iq,linecode,pat_sel};a_r_ok<=1'b1;
  end
`endif
`endif
 // Admission uses only the registered, conservative ready (no backpressure:
 // a refused word faults the receiver). SPARE=4 covers the collector's input and output registers.
 pt_cdc_fifo #(.W(40),.A(EGRESS_A),.DEPTH(EGRESS_DEPTH),.SPARE(4),.MEMORY(2),.POPQ(1),.CNTPIPE(1)) egress(
  .wr_clk(host_clk),.rd_clk(egress_clk),.rst_n(frst),
  .din(rx_quad),.push(rx_push&&!mem_play),.pop(egress_pop),
  .dout(egress_head),.full(egress_full),.empty(egress_empty),.nonempty(egress_ne),.ready(egress_ready),.rd_count(egress_count),
  .overflow(egress_ov),.underflow(egress_un),.wr_active(),.rd_active(),.wr_ptr(),.rd_ptr(),
  .peek_idx(5'd0),.peek(),.play(mem_play),.play_loop(mem_loop),.play_last(mem_last),
  .spi_clk(spi_clk),.spi_we(mem_we),.spi_idx(mem_idx),.spi_d(mem_wdata));
 assign wire_ready=egress_ready;assign iq_ready=egress_ready;
 // ---------------- wired output (wire_tx_clk = WORD_CLK40). The serializer
 // loads D0..D19 a fraction of a period after WORD_CLK40 rises and D20..D39
 // one 20-bit word later: the low half comes from falling-edge flops (launched
 // half a period early), the high half from rising-edge flops.
 reg idle_command,mute_command,command_fault;
 wire rx_fault_wire,rx_fault_rf,idle_sync,mute_sync;
 pt_sync_bit f0(wire_tx_clk,rst_n,rx_fault||command_fault,rx_fault_wire);
 pt_sync_bit f1(rf_tx_clk,rst_n,rx_fault||command_fault,rx_fault_rf);
 pt_sync_bit f2(wire_tx_clk,rst_n,idle_command,idle_sync);
 pt_sync_bit f3(rf_tx_clk,rst_n,mute_command,mute_sync);
 // IX-2 8b/10b transmit offload (wire_tx_clk): a registered FWFT head in front of the serializer
 wire wire_out_empty=payload_iq||(linecode?!lc_qv:egress_empty);
 pt_lc_tx lc_tx(.clk(wire_tx_clk),.rst_n(rst_n),.en(linecode&&ewt&&!payload_iq),.head(egress_head),.head_valid(egress_ne),
  .pop(lc_pop),.q(lc_q),.q_valid(lc_qv),.take(wreq&&wire_running&&lc_qv));   // = !wire_out_empty while linecode
 wire[39:0]wire_head=linecode?lc_q:egress_head;
 wire[EGRESS_A:0]wire_out_count=payload_iq?0:egress_count;
 reg[19:0]wire_low,wire_high;
 wire[39:0]lane_out=pat_sel?pat_word:payload_iq?40'd0:wire_head;
 // Output stage (timing 2026-11-11, coordinator decision for wtx): the lane word and its valid / idle
 // are registered once (lane_q / wire_valid_q / wire_idle_q, rising WORD_CLK40) before the launch flops,
 // as a one-entry valid/ready stage: it loads when empty or when the serializer takes the word
 // (wire_tx_request && wire_tx_valid), an untaken word is held, and the sources (egress / 8b10b /
 // pattern) see the stage's load as their request. Port protocol unchanged (a word transfers on a
 // clock with request && valid); data and valid both one WORD_CLK40 later, and the WT20 D-bus launch
 // is unchanged (D0..D19 from wire_low on the fall, D20..D39 from wire_high on the rise, both from
 // lane_q). No egress-empty -> output-port path, and wire_low no longer takes the head / pattern
 // select on a half-period path. valid / idle clear asynchronously on disable (rst_n && enable), as
 // the combinational valid did through the bank reset, without needing the host clock.
 reg[39:0]lane_q;reg wire_valid_q,wire_idle_q;
 assign wire_load=!wire_valid_q||wire_tx_request;
 assign wire_req_int=wire_load;
 assign wreq=wire_load&&!pat_sel;
 wire wire_valid_n=wire_running&&!wire_out_empty&&!rx_fault_wire&&!wire_starved;
 wire stage_valid_n=wire_load?(pat_sel?pat_valid:wire_valid_n):wire_valid_q;
 wire out_rst_n=rst_n&&enable;
 always @(posedge wire_tx_clk or negedge out_rst_n)
  if(!out_rst_n)begin wire_valid_q<=1'b0;wire_idle_q<=1'b1;end
  else begin wire_valid_q<=stage_valid_n;wire_idle_q<=pat_sel?pat_idle:(!stage_valid_n||idle_sync);end
 always @(posedge wire_tx_clk or negedge rst_n)
  if(!rst_n)lane_q<=0;else if(wire_load)lane_q<=lane_out;
 always @(negedge wire_tx_clk or negedge rst_n)
  if(!rst_n)wire_low<=0;else wire_low<=lane_q[19:0];
 always @(posedge wire_tx_clk or negedge rst_n)
  if(!rst_n)wire_high<=0;else wire_high<=lane_q[39:20];
 assign wire_tx_data={wire_high,wire_low};
 assign wire_tx_valid=wire_valid_q;
 assign wire_idle=wire_idle_q;
 assign wire_running_n=ewt&&(wire_running||wire_out_count>=WIRE_START);   // next wire_running
 always @(posedge wire_tx_clk or negedge rst_n)begin
  if(!rst_n)begin wire_running<=0;wire_starved<=0;end
  else if(!ewt)begin wire_running<=0;wire_starved<=0;end
  else if(!wire_running&&wire_out_count>=WIRE_START)wire_running<=1;
  else if(wire_running&&wreq&&wire_out_empty)wire_starved<=1;
 end
 // ---------------- RF output: quads unpacked into one sample per request in
 // the sample-clock domain (reservoir reset while the domain is disabled; it
 // prefetches before the start threshold so the first request finds a sample).
 wire rf_out_empty=!payload_iq||egress_empty;
 wire[23:0]rf_out_head;wire rf_sample_ready;
 pt_sample_unpack unpacker(rf_tx_clk,rst_n&&ert,mode8,egress_head,payload_iq&&!egress_empty,
  rf_unpack_ready,rf_out_head,rf_sample_ready,rf_tx_request&&rf_tx_valid);
 assign rf_tx_sample=mode8?{rf_out_head[15:8],4'd0,rf_out_head[7:0],4'd0}:rf_out_head;
 assign rf_tx_valid=rf_running&&rf_sample_ready&&!rx_fault_rf&&!rf_starved;
 assign rf_mute=!rf_tx_valid||mute_sync;
 always @(posedge rf_tx_clk or negedge rst_n)begin
  if(!rst_n)begin rf_running<=0;rf_starved<=0;end
  else if(!ert)begin rf_running<=0;rf_starved<=0;end
  // egress rd_count is pipelined (CNTPIPE): it can miss the last two pops, and the unpacker prefetches
  // before rf_running, so the start threshold carries +2 (same or more quads than RF_START at the start).
  else if(!rf_running&&rf_sample_ready&&egress_count>=RF_START+2)rf_running<=1;
  else if(rf_running&&rf_tx_request&&!rf_sample_ready)rf_starved<=1;
 end
 // opcode4 commit: one pending update only; a command arriving before the previous gain-status
 // frame was sent is rejected without changing gain (sticky status), never deferred.
 assign gain_commit=command_valid&&opcode==4'd4&&payload_iq&&!gain_pending;
 always @(posedge host_clk or negedge rst_n)begin
  if(!rst_n)begin idle_command<=0;mute_command<=0;command_fault<=0;
   gain_toggle<=0;gain_pending<=0;gain_rejected<=0;gain_arg<=0;mark_ack<=0;end
  else if(!eh)begin idle_command<=0;mute_command<=0;command_fault<=0;
   gain_pending<=0;gain_rejected<=0;mark_ack<=mark_sync;end
  else begin
   if(command_valid)case(opcode)
    0:begin end
    1:if(argument<=1)idle_command<=argument[0];else command_fault<=1;
    2:if(argument<=1)mute_command<=argument[0];else command_fault<=1;
    4:if(!payload_iq)command_fault<=1;
      else if(gain_pending)gain_rejected<=1;
      else begin gain_arg<=argument[6:0];gain_toggle<=!gain_toggle;gain_pending<=1;end
    default:command_fault<=1;
   endcase
   if(gain_echo)begin gain_pending<=0;mark_ack<=mark_sync;end
  end
 end
 wire wire_out_ov=!payload_iq&&egress_ov,wire_out_un=!payload_iq&&egress_un;
 wire rf_out_ov=payload_iq&&egress_ov,rf_out_un=payload_iq&&egress_un;
 // Bits 4/5 (formerly the paired core's I/Q queues) are owner-multiplexed: RF ownership
 // {5: fast gain pending, 4: fast gain rejected (sticky)}; wired ownership {5: 8b/10b aligned,
 // 4: 8b/10b code error (sticky)}. Raw multi-domain levels, synchronized by the register file.
 wire[1:0]owner_bits=payload_iq?{gain_pending,gain_rejected}:{lc_aligned,lc_code_error};
 assign status={3'd0,rf_starved,wire_starved,command_fault,locked,rx_fault,
  rf_out_ov,wire_out_ov,owner_bits,rf_ov,wr_ov,(rf_un||wr_un||rf_out_un||wire_out_un),enable};
endmodule

// Fast gain, RF RX sample domain. A change of the (synchronized) commit toggle applies the new gain
// (held stable in the hcore domain until the gain-status frame) at this clock, discards the packer
// reservoir (the samples not completely delivered: `base` nibbles) and the next SETTLE valid samples,
// then records the ingress write pointer where the first new-gain quad will land (mark_ptr) and
// flips mark_toggle. No quad is pushed between the flush and that first quad, so mark_ptr is exact.
// gap = discarded complex pairs (partial ones included), <= 3 + SETTLE <= 127.
module pt_gain_rx #(parameter A=5,SETTLE=20)(input wire clk,rst_n,toggle,input wire[6:0]gain_h,
 input wire mode8,input wire[3:0]base,input wire valid,input wire[A:0]wr_ptr,
 output wire flush,drop,output reg[6:0]gain,output reg active,output reg[6:0]gap,
 output reg[A:0]mark_ptr,output reg mark_toggle);
 (* async_reg="true" *) reg t1,t2;reg t3,settling;reg[5:0]left;
 always @(posedge clk or negedge rst_n)if(!rst_n)begin t1<=0;t2<=0;end else begin t1<=toggle;t2<=t1;end
 // change is a REGISTER (timing 2026-11-11, rfrx: t2 ^ t3 -> flush -> 60-bit packer reservoir and
 // the drop gate): the commit toggle takes effect one rf_rx clock later (a third synchronizer
 // stage in effect); flush, drop, gain, gap and mark_ptr all follow the same registered change.
 reg change;
 // pairs not completely delivered: ceil(base / nibbles-per-pair)
 wire[3:0]base3=base+4'd3;
 wire[2:0]partial=mode8 ? {1'b0,base3[3:2]} : (base==4'd0) ? 3'd0 : (base<=4'd6) ? 3'd1 : 3'd2;
 assign flush=change;
 assign drop=change||settling;
 always @(posedge clk or negedge rst_n)
  if(!rst_n)begin t3<=0;change<=0;settling<=0;left<=0;gain<=0;active<=0;gap<=0;mark_ptr<=0;mark_toggle<=0;end
  else begin
   t3<=t2;change<=t2!=t3;
   if(change)begin
    gain<=gain_h;active<=1;settling<=1;
    gap<={4'd0,partial}+{6'd0,valid};left<=SETTLE[5:0]-{5'd0,valid};
   end else if(settling&&valid)begin
    gap<=gap+1'b1;left<=left-1'b1;
    if(left==6'd1)begin settling<=0;mark_ptr<=wr_ptr;mark_toggle<=!mark_toggle;end
   end
  end
endmodule
