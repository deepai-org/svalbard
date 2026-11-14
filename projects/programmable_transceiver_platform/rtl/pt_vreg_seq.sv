// Ring-PLL regulator sequencing (PD9 / RA-17, pt_pll_vreg). REF_CLK domain.
// A regulated ring (pllvreg.config.{tx,rx}_bypass = 0) must not be enabled until its regulator output
// has settled (start-up <= 37 us to 5 %). A wait of >= 50 us starts when the pll island comes on
// (island_on rising) or when either regulator leaves bypass; while it runs, the enables of the
// regulated rings are held low (tx_ok / rx_ok = 0). Bypassed rings (the reset state) are never held.
// 5000 + 2 REF cycles: >= 50 us for any REF_CLK <= 100 MHz (longer for a slower reference). The
// timer is a 13-bit LFSR (one XOR level; no carry chain at the reference rate).
// The inputs are SCLK-domain levels (register file outputs): two-flop synchronized here. A missing
// REF_CLK keeps a regulated ring off; use bypass (the reset state) for reference-less bring-up.
`default_nettype none
module pt_vreg_seq(
    input  wire rst_n,
    input  wire ref_clk,
    input  wire pll_on,      // island_on[pll]
    input  wire tx_bypass,   // pllvreg.config.tx_bypass (island-gated: 0 while the island is off)
    input  wire rx_bypass,   // pllvreg.config.rx_bypass
    output wire tx_ok,       // 1: the TX/host ring enable may pass
    output wire rx_ok        // 1: the CDR ring enable may pass
);
    localparam [12:0] SEED = 13'h042F, TPRE = 13'h1FFF;   // 5000 LFSR steps SEED -> TPRE
    wire on_s, txb_s, rxb_s;
    pt_sync_bit s0(.clk(ref_clk), .rst_n(rst_n), .d(pll_on), .q(on_s));
    pt_sync_bit s1(.clk(ref_clk), .rst_n(rst_n), .d(tx_bypass), .q(txb_s));
    pt_sync_bit s2(.clk(ref_clk), .rst_n(rst_n), .d(rx_bypass), .q(rxb_s));
    reg on_d, txb_d, rxb_d, waiting, tick, trig_q;
    reg [12:0] lfsr;
    wire trigger = (on_s && !on_d) || (txb_d && !txb_s) || (rxb_d && !rxb_s);
    always @(posedge ref_clk or negedge rst_n)
        if (!rst_n) begin
            on_d <= 1'b0; txb_d <= 1'b0; rxb_d <= 1'b0; waiting <= 1'b0; tick <= 1'b0; trig_q <= 1'b0; lfsr <= SEED;
        end else begin
            on_d <= on_s; txb_d <= txb_s; rxb_d <= rxb_s;
            trig_q <= trigger;                 // registered: keeps the edge decode off the LFSR load path
            tick <= waiting && !trig_q && lfsr == TPRE;
            if (trig_q) begin waiting <= 1'b1; lfsr <= SEED; end
            else if (tick) waiting <= 1'b0;
            else if (waiting) lfsr <= {lfsr[11:0], lfsr[12] ^ lfsr[3] ^ lfsr[2] ^ lfsr[0]};
        end
    // Review 2026-11-14 (finding 6): the ok levels were an OR of flops that swap on one edge (a 50 ns enable runt when
    // the island came on with a regulated ring pre-enabled) and were 1 after reset with no reference clock. Now one
    // flop per ring, reset 0, set only by a completed wait with the island on and the ring out of bypass, cleared by
    // any new trigger; a bypassed ring is passed by the raw (static) bypass level, so reference-less bring-up in
    // bypass still works and a regulated ring stays off without REF_CLK.
    reg rdy_tx, rdy_rx;
    wire hold = trigger || trig_q || !on_s;
    always @(posedge ref_clk or negedge rst_n)
        if (!rst_n) begin rdy_tx <= 1'b0; rdy_rx <= 1'b0; end
        else begin
            rdy_tx <= !hold && !txb_s && !txb_d && (rdy_tx || tick);
            rdy_rx <= !hold && !rxb_s && !rxb_d && (rdy_rx || tick);
        end
    assign tx_ok = tx_bypass | rdy_tx;
    assign rx_ok = rx_bypass | rdy_rx;
endmodule
`default_nettype wire
