// Formal harness for rtl/pt_clocktree_slow.sv (P2-10), serializer-clock core
// pt_ct_word with free synchronized inputs, and the detector divider rule.
// Run via verification/run_clocktree_slow_formal.sh (SymbiYosys, yices).
//   W1 divider phase in range; word_load/word_clk decode the phase
//   W2 phase advances modulo M except at a launch re-phase
//   W3 launch re-phase exactly 10*word + bit UI (or (10w+b)/2 half-rate cycles)
//      after the accepted reference edge; at most one launch in flight; ser_run,
//      word zero and bit_phase at the re-phase; ser_run never falls
//   W4 qualified only with lock and only after QUAL consecutive good edges
//   D1 detector N = ceil(rate / 500 MHz) clamped to 1..5, or the explicit code
module pt_clocktree_slow_fv(
    input wire clk,
    input wire half, input wire [3:0] bitd, input wire [1:0] wordd,
    input wire nref_rise, npend, lock,   // free; ref_rise/pend are their registered copies (as the
                                         // parent's synchronizer stages), lreq_next = nref_rise && npend
    input wire [2:0] ddiv, input wire [21:0] rate
);
    localparam integer Q = 4;
    reg ref_rise = 1'b0, pend = 1'b0;
    always @(posedge clk) begin ref_rise <= nref_rise; pend <= npend; end
    reg init = 1'b1;
    always @(posedge clk) init <= 1'b0;
    wire rst_n = !init;
    always @(posedge clk) if (!init) begin
        assume ($stable(half)); assume ($stable(bitd)); assume ($stable(wordd));
    end
    // pend reaches pt_ct_word through a two-flop synchronizer released by the same reset: it is 0
    // in the first clock after reset (the registered d_cyc decodes dc0/dn0 are valid from then on).
    // (TC6: also through the second, since the registered rephase uses the d_cyc decode one clock
    // ahead; in hardware pend stays 0 for >= 64 reference periods after reset: arm needs qualified.)
    reg first = 1'b1, second = 1'b1;   // 1 through the first two clocks after reset release
    always @(posedge clk) begin first <= init; second <= first; end
    always @* if (first || second) assume (!pend);

    wire [3:0] cnt, since; wire word_clk, word_load, ser_run, bit_phase, launching, qualified; wire [6:0] stable; wire [5:0] dly;
    pt_ct_word #(.QUAL_CYCLES(Q)) dut(.wclk(clk), .rst_n(rst_n), .cfg_half_rate(half), .cfg_bit_delay(bitd),
        .cfg_word_delay(wordd), .ref_rise(ref_rise), .pend(pend), .lreq_next(nref_rise && npend), .lock(lock), .cnt(cnt), .word_clk(word_clk),
        .word_load(word_load), .ser_run(ser_run), .bit_phase(bit_phase), .launching(launching),
        .qualified(qualified), .stable(stable), .since(since), .dly(dly));

    // independent reference model
    wire [3:0] m_last = half ? 4'd4 : 4'd9;
    wire [5:0] ui     = 6'd10 * wordd + (bitd > 9 ? 6'd9 : {2'b0, bitd});
    wire [5:0] d      = half ? ui >> 1 : ui;
    reg        f_inflight; reg [5:0] f_t;
    wire       f_launch  = rst_n && ref_rise && pend && !f_inflight;
    wire       f_rephase = (f_launch && d == 0) || (f_inflight && f_t == d);
    always @(posedge clk) begin
        if (!rst_n) begin f_inflight <= 1'b0; f_t <= 0; end
        else if (f_launch && d != 0) begin f_inflight <= 1'b1; f_t <= 6'd1; end
        else if (f_inflight && f_t == d) f_inflight <= 1'b0;
        else if (f_inflight) f_t <= f_t + 6'd1;
    end
    // consecutive good reference edges
    reg [7:0] f_good; reg [3:0] f_since;
    reg [7:0] f_good_d, f_good_d2;   // pipeline copies (stable / qualified latency)
    always @(posedge clk) begin f_good_d <= rst_n ? f_good : 8'd0; f_good_d2 <= rst_n ? f_good_d : 8'd0; end
    always @(posedge clk) begin
        if (!rst_n) begin f_good <= 0; f_since <= 4'hf; end
        else begin
            if (ref_rise) f_since <= 0; else if (f_since != 4'hf) f_since <= f_since + 1'b1;
            if (!lock || f_since == 4'hf) f_good <= 0;
            else if (ref_rise) f_good <= (f_since == m_last) ? (f_good == 8'hff ? f_good : f_good + 1'b1) : 8'd0;
        end
    end

    always @(posedge clk) if (rst_n) begin
        // W1
        assert (cnt <= m_last);
        assert (launching == f_inflight);
        if ($past(rst_n)) begin
            // decode registers are consistent from the first clock after reset
            assert (word_load == (cnt == 0));
            assert (word_clk == (cnt < (half ? 4'd2 : 4'd5)));
            // W2 / W3
            if ($past(f_rephase)) begin
                assert (cnt == 0 && ser_run && word_load);
                assert (bit_phase == (half & ui[0]));
            end else begin
                assert (cnt == ($past(cnt) >= $past(m_last) ? 4'd0 : $past(cnt) + 4'd1));
                assert (bit_phase == $past(bit_phase));
            end
            if ($past(ser_run)) assert (ser_run);
            if (!$past(ser_run) && !$past(f_rephase)) assert (!ser_run);
        end
        // W4 (TC6 timing pipeline): stable follows the reference count one clock late and
        // `qualified` one further clock (registered): qualified only with lock, after Q good edges.
        if ($past(rst_n)) assert (stable == (f_good_d > Q ? Q : f_good_d));
        if ($past(rst_n) && $past(rst_n, 2)) assert (qualified == (f_good_d2 >= Q));
        assert (stable <= Q);
        assert (since == f_since);
        if (f_inflight) assert (f_t >= 1 && f_t <= d && dly == d - f_t);
    end
    always @(posedge clk) if (rst_n) begin
        cover (qualified && ser_run && word_load && !half && d == 39);
        cover (ser_run && bit_phase && half);
    end

    // D1: detector divider rule (combinational part)
    wire [2:0] div;
    pt_ct_detect_rule det(.cfg_div(ddiv), .cfg_rate_khz(rate), .div(div));
    always @* begin
        assert (div >= 1 && div <= 5);
        if (ddiv == 0 && rate >= 1 && rate <= 22'd2500000)
            assert (25'd500000 * div >= rate && 25'd500000 * (div - 1) < rate);
        if (ddiv == 0 && rate > 22'd2500000) assert (div == 5);
        if (ddiv != 0) assert (div == (ddiv > 5 ? 3'd5 : ddiv));
    end
endmodule
