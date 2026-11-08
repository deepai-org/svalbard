// Clock-tree slow functions in standard cells (spec/consolidation-pass.md P2-10;
// gap 6 of analog/timing/README.md):
//   * serializer word divider: /10 of the bit clock, or /5 of the half-rate clock
//     (cfg_half_rate=1; the analog final DDR 2:1 mux supplies the last /2 and the
//     odd launch bit through `bit_phase`);
//   * 64-reference-cycle alignment qualification and the phase-qualified
//     divider/serializer reset release used by deterministic multi-chip launch
//     (spec/block-diagram.md "Deterministic multi-chip launch", clocktree.config
//     sync_arm / launch_reference_count / launch_word_delay / launch_bit_delay);
//   * wired detector clock divider ceil(f_wire / 500 MHz) (analog-architecture
//     blocks.clocktree.parameters.detector_divider_rule), 50 % duty for odd N.
// The fast /2, /4 wire-clock chain, ALIGN_STATUS/WORD_EPOCH and the clock muxes
// stay in the transistor-level pt_clocktree; this replaces only its
// power-of-two approximations. Configuration inputs are static (update: stopped).
`default_nettype none

// ---------------------------------------------------------------------------
// Serializer-clock domain core: word divider, phase-window qualification and
// launch re-phasing. Inputs ref_rise/pend/lock are already synchronized to wclk.
module pt_ct_word #(parameter integer QUAL_CYCLES = 64)(
    input  wire       wclk,
    input  wire       rst_n,         // async assert; release synchronous to wclk
    input  wire       cfg_half_rate, // 0: modulus 10 on the bit clock; 1: modulus 5 on the half-rate clock
    input  wire [3:0] cfg_bit_delay, // 0..9 UI   (values > 9 behave as 9)
    input  wire [1:0] cfg_word_delay,// 0..3 words
    input  wire       ref_rise,      // one wclk cycle per reference rising edge (synchronized)
    input  wire       pend,          // launch request from the reference domain (synchronized)
    input  wire       lock,          // analog PLL lock / phase-window indication (synchronized)
    output reg  [3:0] cnt,           // word-divider phase, 0..M-1
    output reg        word_clk,      // M/2 (or 2 of 5) cycles high, rises at word zero
    output reg        word_load,     // high in the cycle cnt == 0 (serializer parallel load)
    output reg        ser_run,       // serializer reset release; set at the launched word zero
    output reg        bit_phase,     // half-rate: start on the second DDR half (odd delay)
    output reg        launching,     // launch accepted, delay running
    output wire       qualified,
    output reg  [6:0] stable,        // consecutive good reference cycles (saturating)
    output reg  [3:0] since,         // wclk cycles since the last reference edge (saturating 15)
    output reg  [5:0] dly            // remaining launch delay while `launching`
);
    wire [3:0] m_last = cfg_half_rate ? 4'd4 : 4'd9;
    wire [3:0] bits   = cfg_bit_delay > 4'd9 ? 4'd9 : cfg_bit_delay;
    wire [5:0] d_ui   = {cfg_word_delay, 3'b000} + {cfg_word_delay, 1'b0} + bits;  // 10*w + b, 0..39
    wire [5:0] d_cyc  = cfg_half_rate ? {1'b0, d_ui[5:1]} : d_ui;


    wire launch_ev = ref_rise && pend && !launching;
    wire rephase   = launching ? dly == 0 : (launch_ev && d_cyc == 0);
    wire [3:0] cnt_next = rephase ? 4'd0 : (cnt >= m_last ? 4'd0 : cnt + 4'd1);
    wire [3:0] hi = cfg_half_rate ? 4'd2 : 4'd5;

    // Phase window: the reference edge must land in the same wclk cycle every
    // period, i.e. exactly M cycles apart. With a free-running modulus-M divider
    // this is equivalent to a constant divider phase at the edge, and it is
    // unaffected by the deliberate launch re-phase. Resolution is one wclk cycle;
    // the sub-UI 0.0625 UI target is the analog PFD/lock detector's (`lock`).
    wire period_ok = since == m_last;
    wire good      = lock && period_ok;
    assign qualified = stable == QUAL_CYCLES;

    always @(posedge wclk or negedge rst_n) begin
        if (!rst_n) begin
            cnt <= 0; word_clk <= 1'b0; word_load <= 1'b0; ser_run <= 1'b0; bit_phase <= 1'b0;
            launching <= 1'b0; dly <= 0; since <= 4'hf; stable <= 0;
        end else begin
            cnt       <= cnt_next;
            word_load <= cnt_next == 0;
            word_clk  <= cnt_next < hi;
            // launch: fixed latency from the qualified reference edge, then d_cyc cycles
            if (launch_ev && d_cyc != 0) begin launching <= 1'b1; dly <= d_cyc - 6'd1; end
            else if (launching && dly != 0) dly <= dly - 6'd1;
            else if (launching) launching <= 1'b0;
            if (rephase) begin ser_run <= 1'b1; bit_phase <= cfg_half_rate & d_ui[0]; end
            // qualification
            if (ref_rise) since <= 0; else if (since != 4'hf) since <= since + 4'd1;
            if (!lock || since == 4'hf) stable <= 0;
            else if (ref_rise) stable <= !good ? 7'd0 : (stable == QUAL_CYCLES ? stable : stable + 7'd1);
        end
    end
endmodule

// ---------------------------------------------------------------------------
// Reference-domain launch sequencer: arm (sync_arm rising while qualified), marker
// capture on a reference edge, launch_reference_count edges, then a launch
// request held for one reference period and re-timed on the falling edge so the
// wclk side samples it half a reference period before the launching edge.
module pt_ct_launch(
    input  wire        ref_clk,
    input  wire        rst_n,
    input  wire        arm,          // synchronized sync_arm level
    input  wire        qualified,    // synchronized from the wclk domain
    input  wire        marker,       // ALIGN_MARKER, board-timed to the reference capture edge
    input  wire [15:0] cfg_ref_count,// 4..65535 (smaller values behave as 4)
    output reg         armed,
    output reg         counting,
    output reg         marker_seen,  // sticky
    output reg         launched,     // sticky until the next arm
    output reg         arm_fault,    // sticky: qualification lost while armed/counting
    output reg         pend_n        // to the wclk domain (falling-edge register)
);
    reg        marker_q, marker_d, arm_d, req;
    reg [15:0] rc;
    wire [15:0] n = cfg_ref_count < 16'd4 ? 16'd4 : cfg_ref_count;
    wire mrise = marker_q && !marker_d;
    always @(posedge ref_clk or negedge rst_n) begin
        if (!rst_n) begin
            marker_q <= 0; marker_d <= 0; arm_d <= 0; req <= 0; rc <= 0;
            armed <= 0; counting <= 0; marker_seen <= 0; launched <= 0; arm_fault <= 0;
        end else begin
            marker_q <= marker; marker_d <= marker_q; arm_d <= arm; req <= 1'b0;
            if (mrise) marker_seen <= 1'b1;
            if ((armed || counting) && !qualified) begin
                armed <= 0; counting <= 0; arm_fault <= 1'b1;
            end else if (arm && !arm_d && qualified && !counting) begin
                armed <= 1'b1; launched <= 1'b0; arm_fault <= 1'b0;
            end else if (armed && mrise) begin
                armed <= 1'b0; counting <= 1'b1; rc <= 16'd1;   // this is capture edge + 1
            end else if (counting) begin
                rc <= rc + 16'd1;
                if (rc + 16'd1 == n - 16'd1) begin req <= 1'b1; counting <= 1'b0; launched <= 1'b1; end
            end
        end
    end
    always @(negedge ref_clk or negedge rst_n)
        if (!rst_n) pend_n <= 1'b0; else pend_n <= req;
endmodule

// ---------------------------------------------------------------------------
// Detector divider rule: N = ceil(rate / 500 MHz), clamped to 1..5, or explicit.
module pt_ct_detect_rule(
    input  wire [2:0]  cfg_div,      // 0: rule from cfg_rate_khz; 1..5 explicit (6, 7 -> 5)
    input  wire [21:0] cfg_rate_khz,
    output wire [2:0]  div
);
    wire [2:0] rule = cfg_rate_khz <= 22'd500000  ? 3'd1 :
                      cfg_rate_khz <= 22'd1000000 ? 3'd2 :
                      cfg_rate_khz <= 22'd1500000 ? 3'd3 :
                      cfg_rate_khz <= 22'd2000000 ? 3'd4 : 3'd5;
    assign div = cfg_div == 0 ? rule : (cfg_div > 3'd5 ? 3'd5 : cfg_div);
endmodule

// ---------------------------------------------------------------------------
// Detector clock: wire clock / N, N = ceil(rate / 500 MHz) in 1..5, or explicit.
module pt_ct_detect_div(
    input  wire        clk,          // selected TX wire clock
    input  wire        rst_n,
    input  wire        en,           // synchronized enable
    input  wire [2:0]  cfg_div,      // 0: rule from cfg_rate_khz; 1..5 explicit (6, 7 -> 5)
    input  wire [21:0] cfg_rate_khz, // wire clock in kHz (480000..2500000)
    output wire [2:0]  div,          // applied N
    output wire        det_clk
);
    pt_ct_detect_rule rule_i(.cfg_div(cfg_div), .cfg_rate_khz(cfg_rate_khz), .div(div));

    reg [2:0] n_q, c;
    reg       a, b, en_n;
    wire [2:0] c_next = c >= n_q - 3'd1 ? 3'd0 : c + 3'd1;
    wire [2:0] half   = (n_q + 3'd1) >> 1;          // high cycles of `a`
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin n_q <= 3'd1; c <= 0; a <= 0; end
        else if (!en) begin n_q <= div; c <= 0; a <= 0; end
        else begin c <= c_next; a <= c_next < half; end
    end
    // b: `a` half a cycle later (odd-N 50 % duty). en_n: falling-edge enable, so the
    // N = 1 gate clk & en_n only changes while clk is low (glitch-free, no latch).
    always @(negedge clk or negedge rst_n) if (!rst_n) begin b <= 0; en_n <= 0; end else begin b <= a; en_n <= en; end
    assign det_clk = n_q == 3'd1 ? (clk & en_n) : (n_q[0] ? (a & b) : a);
endmodule

// ---------------------------------------------------------------------------
module pt_clocktree_slow #(parameter integer QUAL_CYCLES = 64)(
    input  wire        rst_n,         // async; each domain has its own release synchronizer
    // serializer word clock
    input  wire        wclk,          // bit clock (cfg_half_rate=0) or half-rate clock
    input  wire        cfg_half_rate,
    input  wire [3:0]  cfg_bit_delay,  // clocktree.config.launch_bit_delay
    input  wire [1:0]  cfg_word_delay, // clocktree.config.launch_word_delay
    input  wire        pll_lock,       // async
    output wire        word_clk, word_load, ser_run, bit_phase, qualified,
    // reference / launch
    input  wire        ref_clk,        // forwarded word reference (line rate / 10)
    input  wire        marker,         // ALIGN_MARKER
    input  wire        cfg_sync_arm,   // clocktree.config.sync_arm (async level)
    input  wire [15:0] cfg_ref_count,  // clocktree.config.launch_reference_count
    output wire        armed, marker_seen, launched, arm_fault,
    // wired detector clock
    input  wire        det_clk_in,
    input  wire        cfg_det_en,     // async
    input  wire [2:0]  cfg_det_div,
    input  wire [21:0] cfg_rate_khz,
    output wire [2:0]  det_div,
    output wire        det_clk
);
    // per-domain reset release
    reg [1:0] wr, rr, dr;
    always @(posedge wclk or negedge rst_n)       if (!rst_n) wr <= 0; else wr <= {wr[0], 1'b1};
    always @(posedge ref_clk or negedge rst_n)    if (!rst_n) rr <= 0; else rr <= {rr[0], 1'b1};
    always @(posedge det_clk_in or negedge rst_n) if (!rst_n) dr <= 0; else dr <= {dr[0], 1'b1};

    // synchronizers into wclk: reference (as data), launch request, lock
    (* async_reg = "true" *) reg [2:0] ref_s;
    (* async_reg = "true" *) reg [1:0] pend_s, lock_s;
    wire pend_n;
    always @(posedge wclk or negedge wr[1])
        if (!wr[1]) begin ref_s <= 0; pend_s <= 0; lock_s <= 0; end
        else begin ref_s <= {ref_s[1:0], ref_clk}; pend_s <= {pend_s[0], pend_n}; lock_s <= {lock_s[0], pll_lock}; end
    wire [3:0] cnt, since; wire launching; wire [6:0] stable; wire [5:0] dly;
    pt_ct_word #(.QUAL_CYCLES(QUAL_CYCLES)) word(.wclk(wclk), .rst_n(wr[1]), .cfg_half_rate(cfg_half_rate),
        .cfg_bit_delay(cfg_bit_delay), .cfg_word_delay(cfg_word_delay), .ref_rise(ref_s[1] && !ref_s[2]),
        .pend(pend_s[1]), .lock(lock_s[1]), .cnt(cnt), .word_clk(word_clk), .word_load(word_load),
        .ser_run(ser_run), .bit_phase(bit_phase), .launching(launching), .qualified(qualified), .stable(stable), .since(since), .dly(dly));

    // synchronizers into ref_clk: sync_arm, qualified
    (* async_reg = "true" *) reg [1:0] arm_s, qual_s;
    always @(posedge ref_clk or negedge rr[1])
        if (!rr[1]) begin arm_s <= 0; qual_s <= 0; end
        else begin arm_s <= {arm_s[0], cfg_sync_arm}; qual_s <= {qual_s[0], qualified}; end
    wire counting;
    pt_ct_launch launch(.ref_clk(ref_clk), .rst_n(rr[1]), .arm(arm_s[1]), .qualified(qual_s[1]), .marker(marker),
        .cfg_ref_count(cfg_ref_count), .armed(armed), .counting(counting), .marker_seen(marker_seen),
        .launched(launched), .arm_fault(arm_fault), .pend_n(pend_n));

    (* async_reg = "true" *) reg [1:0] den_s;
    always @(posedge det_clk_in or negedge dr[1]) if (!dr[1]) den_s <= 0; else den_s <= {den_s[0], cfg_det_en};
    pt_ct_detect_div detect(.clk(det_clk_in), .rst_n(dr[1]), .en(den_s[1]), .cfg_div(cfg_det_div),
        .cfg_rate_khz(cfg_rate_khz), .div(det_div), .det_clk(det_clk));
endmodule
`default_nettype wire
