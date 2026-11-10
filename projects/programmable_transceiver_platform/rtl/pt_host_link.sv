// Host GPIO link logic (hostio, digital half). The provider gf180mcu_fd_io pad cells
// (bi_24t / bi_t, in_c, in_s at the contract.json assembly_policy sites) own the electrical
// pad: ESD, level, drive, slew, pulls and the PAD->Y receiver. Everything clocked lives here and
// is hardened inside pt_digital_macro:
//   * H2D capture on the forwarded H2D_CLK (pin clock): rising-edge register r and, in DDR mode,
//     falling-edge register f. Word order on the pins: word 0 with the rising edge, word 1 with
//     the following falling edge (DDR); one word per rising edge (SDR).
//   * The captured pair {word1, word0} crosses into the core host word clock through a
//     Gray-pointer async FIFO (pt_async_fifo, 2-flop synchronizers) and is replayed one word per
//     word clock. The FPGA derives H2D timing from D2H (pin plan "synchronous profile"), so the
//     two clocks are mesochronous; the FIFO absorbs phase, not a frequency offset.
//   * D2H launch on the word clock rising edge (registered, only flop clock-to-output reaches
//     the pad). Forwarded D2H_CLK, centre aligned:
//       DDR (mode 0): toggle flop on the word-clock FALLING edge -> D2H_CLK = word clock / 2 with
//                     its edges in the middle of each data word.
//       SDR (mode 1, 2): inverted word clock, gated glitch-free by d2h_enable synchronized on the
//                     rising edge (enable changes only while the inverted clock is low). The FPGA
//                     captures on its rising D2H_CLK edge = our falling edge = mid-word.
//   * Mode 2 (reduced-rate SDR) is mode 1 logic on a slower word clock chosen by the clocktree
//     divider; the pins and logic are identical.
// host_link_mode and d2h_enable are regfile fields: stopped-only / quasi-static (P5 of the
// regfile formal proof). They pass through 2-flop synchronizers here anyway.
// Reset: D2H output enable 0 (pads tristated), data and forwarded clock 0.
`default_nettype none
module pt_host_link(
    input  wire       rst_n,
    input  wire [1:0] mode,          // debug.host_link.mode: 0 DDR, 1 SDR, 2 SDR reduced
    input  wire       d2h_enable,    // hostio.controls.d2h_enable (SCLK domain, quasi-static)
    // H2D pins (pad Y outputs)
    input  wire       h2d_clk,
    input  wire [9:0] h2d_pin,
    // core side, host word clock domain
    input  wire       word_clk,
    output reg  [9:0] h2d_word,
    input  wire [9:0] d2h_word,
    // D2H pins (pad A / OE inputs)
    output reg  [9:0] d2h_pin,
    output wire       d2h_clk_pin,
    output wire       d2h_oe,
    output wire       h2d_overflow, h2d_underflow
);
    // ---------------- H2D: pin-clock domain. The receive path runs whenever its clocks run (it
    // is NOT reset by ENABLE): the stream receiver must be armed before the peer sends its
    // training prefix (spec/streaming-transport-v2.md), so the path adds only its fixed latency.
    // A mode change (stopped only) can slip one word while stopped; ENABLE 0->1 then restarts the
    // frame receiver. Reset assertion is asynchronous; release is synchronized per clock domain.
    wire rx_rst_n = rst_n;
    reg [1:0] hrs, wrs;
    always @(posedge h2d_clk or negedge rx_rst_n) if (!rx_rst_n) hrs <= 2'b00; else hrs <= {hrs[0], 1'b1};
    always @(posedge word_clk or negedge rx_rst_n) if (!rx_rst_n) wrs <= 2'b00; else wrs <= {wrs[0], 1'b1};
    wire hr_n = hrs[1], wr_n = wrs[1];
    wire [1:0] mode_h;
    pt_sync_vec #(2) smh(.clk(h2d_clk), .rst_n(hr_n), .d(mode), .q(mode_h));
    wire ddr_h = mode_h == 2'd0;
    reg [9:0] r, f, h0;
    reg       ph, push;
    reg [19:0] pair;
    always @(negedge h2d_clk or negedge hr_n)
        if (!hr_n) f <= 10'd0; else f <= h2d_pin;
    always @(posedge h2d_clk or negedge hr_n)
        if (!hr_n) begin r <= 10'd0; h0 <= 10'd0; ph <= 1'b0; push <= 1'b0; pair <= 20'd0; end
        else begin
            r  <= h2d_pin;
            ph <= ~ph;
            if (ddr_h) begin pair <= {f, r}; push <= 1'b1; end        // r: rising word, f: next falling word
            else begin h0 <= r; if (ph) begin pair <= {r, h0}; push <= 1'b1; end else push <= 1'b0; end
        end
    // ---------------- H2D: pin clock -> word clock
    wire [19:0] head; wire empty, full; wire [3:0] rd_count;
    reg  pop, run, sel;
    pt_async_fifo #(.W(20), .A(3), .REG_OUT(1)) h2d_fifo(.wr_clk(h2d_clk), .rd_clk(word_clk), .rst_n(rx_rst_n),
        .din(pair), .push(push), .pop(pop), .dout(head), .full(full), .empty(empty),
        .wr_count(), .rd_count(rd_count), .overflow(h2d_overflow), .underflow(h2d_underflow),
        .wr_active(), .rd_active());
    reg [9:0] w1;
    // Start after two pairs are buffered, then replay continuously: word0 then word1 of each pair.
    always @(posedge word_clk or negedge wr_n)
        if (!wr_n) begin run <= 1'b0; sel <= 1'b0; pop <= 1'b0; h2d_word <= 10'd0; w1 <= 10'd0; end
        else begin
            if (!run && rd_count >= 4'd2) run <= 1'b1;
            pop <= 1'b0;
            if (run) begin
                sel <= ~sel;
                if (!sel) begin
                    if (!empty) begin h2d_word <= head[9:0]; w1 <= head[19:10]; pop <= 1'b1; end
                    else h2d_word <= 10'd0;                  // underflow: idle word; flagged by the FIFO
                end else h2d_word <= w1;
            end
        end
    // ---------------- D2H: word clock domain
    wire [1:0] mode_w; wire en_w;
    pt_sync_vec #(3) smw(.clk(word_clk), .rst_n(rst_n), .d({mode, d2h_enable}), .q({mode_w, en_w}));
    always @(posedge word_clk or negedge rst_n)
        if (!rst_n) d2h_pin <= 10'd0; else d2h_pin <= en_w ? d2h_word : 10'd0;
    reg tq, en_ddr;
    always @(negedge word_clk or negedge rst_n)
        if (!rst_n) begin tq <= 1'b0; en_ddr <= 1'b0; end
        else begin en_ddr <= en_w && mode_w == 2'd0; tq <= en_ddr ? ~tq : 1'b0; end
    reg en_sdr;  // rising-edge update: ~word_clk is low then, so the AND below cannot glitch
    always @(posedge word_clk or negedge rst_n)
        if (!rst_n) en_sdr <= 1'b0; else en_sdr <= en_w && mode_w != 2'd0;
    assign d2h_clk_pin = tq | (~word_clk & en_sdr);
    assign d2h_oe = d2h_enable;
endmodule

// Reduced-rate fallback for the whole host transport (debug.host_link.rate):
// 0 = full (core word clock = host word clock), 1 = /2, 2 or 3 = /4. The
// selected clock drives pt_host_link (word side), both paired-core host
// boundaries and every engine behind them, so the chip stays fully
// functional at 1/2 or 1/4 throughput (the FPGA follows the forwarded D2H
// clock; the wired/RF line rates must be lowered to match through the
// clocktree dividers). The field is stopped-only: a change first holds
// the host link and transport core in reset (hold_n=0), switches the
// clock-select register while every destination is in reset, then
// releases. Runt pulses at the switch therefore only reach reset flops.
// STA constrains each setting as a separate mode (HOST_RATE_DIV in
// integration/pt_digital_macro.sdc); the select register is case-analysed.
module pt_host_rate_clock(input wire clk,rst_n,input wire[1:0]rate,
 output wire out_clk,output reg hold_n);
 reg[1:0]div;   // div[0] = clk/2, div[1] = clk/4 (both 50 % duty, rising together)
 reg[1:0]cur;   // applied select: 0 full, 1 /2, 2 /4
 reg[1:0]gap;
 wire[1:0]rate_s;
 pt_sync_vec #(2) rate_sync(clk,rst_n,rate,rate_s);
 reg[1:0]want;   // normalized request, registered (off the 3.2 ns compare path)
 always @(posedge clk or negedge rst_n)
  if(!rst_n)div<=0;else div<=div+1'b1;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin cur<=0;hold_n<=0;gap<=0;want<=0;end
  else begin want<=rate_s[1]?2'd2:rate_s;
  if(hold_n)begin
   if(want!=cur)begin hold_n<=0;gap<=0;end
  end else begin
   gap<=gap+1'b1;
   if(gap==1)cur<=want;
   if(gap==3&&want==cur)hold_n<=1;
  end
  end
 end
 wire slow_clk;
`ifdef SYNTHESIS
 (* keep=1,dont_touch=1 *) gf180mcu_fd_sc_mcu7t5v0__mux2_2 rate_slow_mux(
  .I0(div[0]),.I1(div[1]),.S(cur[1]),.Z(slow_clk));
 (* keep=1,dont_touch=1 *) gf180mcu_fd_sc_mcu7t5v0__mux2_2 rate_clock_mux(
  .I0(clk),.I1(slow_clk),.S(cur != 2'd0),.Z(out_clk));
`else
 assign slow_clk=cur[1] ? div[1] : div[0];
 assign out_clk=(cur != 2'd0) ? slow_clk : clk;
`endif
endmodule

`ifdef SYNTHESIS
(* blackbox *) module gf180mcu_fd_sc_mcu7t5v0__mux2_2(input wire I0,I1,S,output wire Z);
endmodule
`endif
`default_nettype wire
