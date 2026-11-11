`include "pt_regmap_defs.svh"
module pt_digital(input wire rst_n,ref_clk,
 // Host-transport reset: rst_n AND the reduced-rate switch hold (pt_host_rate_clock).
 input wire core_rst_n,
 input wire host_sclk,host_cs_n,host_mosi,output wire host_miso,host_miso_oe,
 input wire host_tx_clk,host_rx_clk,wire_rx_clk,wire_tx_clk,rf_rx_clk,rf_tx_clk,
 // Host transport quads (AC-1): four ten-bit words per host_tx_clk (= host_rx_clk = core clock,
 // host word clock / 4) from/to the pad-edge gearboxes in pt_host_link; word 0 (earliest) in [9:0].
 input wire[39:0]h2d_quad,output wire[39:0]d2h_quad,
 // Wired boundary (AC-1 S3): 40-bit quads, word 0 (earlier on the line) in [9:0], one quad per
 // wire_tx_clk (WORD_CLK40) / wire_rx_clk (WCLK40) edge (<= 62.5 MHz). valid/request are per quad.
 input wire[39:0]wire_rx_data,input wire wire_rx_valid,output wire[39:0]wire_tx_data,
 output wire wire_tx_valid,wire_idle,input wire wire_tx_request,
 input wire[23:0]rf_rx_sample,input wire rf_rx_valid,output wire[23:0]rf_tx_sample,
 output wire rf_tx_valid,rf_mute,input wire rf_tx_request,output wire rf_tx_clk_out,
 output wire enable,mode8,output wire[15:0]rf_trim,wire_trim,clock_trim,
 input wire calibration_above_target,output wire[11:0]calibration_trial,
 output wire[15:0]status,
 // Generated control boundary (rtl/pt_regfile.sv, spec/register-map.md).
 input wire por_n,fault,input wire[`PT_ISLAND_W-1:0]island_pgood,
 // Frequency-counter sources (P3-7), code 1..6 of debug.freq_count_{a,b}.source: [0] tx_ring_fbck (pt_pll
 // FBCK = VCO/16), [1] cdr_ring_fbck, [2] ring_osc, [3] vco_replica, [4] aosc, [5] lc_prescale.
 input wire[5:0]fc_src,
 output wire cdr_freq_locked, // freq_count_b lock (reference domain): CDR frequency-to-phase handover
 input wire[11:0]analog_status,input wire[12:0]wire_analog_status,
 output wire[`PT_ANALOG_CFG_W-1:0]analog_cfg,output wire[`PT_DEBUG_CFG_W-1:0]debug_cfg,
 output wire[`PT_ISLAND_W-1:0]island_en,
 // island_on = switch enabled AND (pgood OR pgood_override): drives every iso_clamp at the core/island
 // boundary (1 = connected, 0 = isolated; reset 0).
 output wire[`PT_ISLAND_W-1:0]island_on,output wire[`PT_ATB_W-1:0]atb0_sw,atb1_sw,
 output wire[`PT_ATB0_GRP_W-1:0]atb0_grp,output wire[`PT_ATB1_GRP_W-1:0]atb1_grp,output wire atb0_en,atb1_en,
 output wire rx_en_aux,rx_en_wclk,rx_en_wtx_ext,clk_obs_oe,wclk_obs_oe,
 output wire dbg_obs0,dbg_obs0_oe,dbg_obs1,dbg_obs1_oe,wdbg_obs,wdbg_obs_oe,commit_toggle,
 // IX-2 8b/10b wired line-code offload (stopped-only level) and the RXR-D2 fast gain (opcode4) state:
 // rf_rx_clk-domain levels; rx_gain = {LNA index[6:5], PGA index[4:0]} as the opcode4 argument.
 input wire linecode,output wire[6:0]rx_gain,output wire rx_gain_active);
 wire memory_write,capture_done,playback_enable,capture_enable,memory_loop;wire[4:0]index,memory_last;
 wire[39:0]memory_wdata,capture_data;
 wire config_error,cal_busy,cal_done,host_rx_div;
 // Observation vectors; order is spec/debug-controls.json obs_status / wire_status. Raw, unsynchronized.
 // analog_status: 0 pll_lock,1 ref_present,2 bias_ready,3 refbuf_ready,4 por_n,5 cdr_qualified,6 cdr_loss,
 // 7 adc_i_done,8 adc_q_done,9 adc_i_overload,10 adc_q_overload,11 aosc_div.
 wire[31:0]obs_status={analog_status[11],host_rx_div,enable,capture_enable,playback_enable,capture_done,cal_done,cal_busy,
  wire_idle,wire_tx_request,wire_rx_valid,rf_mute,rf_tx_request,rf_rx_valid,analog_status[10:5],analog_status[4],fault,
  analog_status[3:0],island_pgood};
 wire[15:0]wire_status={wire_analog_status[12],wire_idle,wire_tx_request,wire_rx_valid,wire_analog_status[11:0]};
 // Pattern checker status (wire_rx_clk domain; pt_mgmt synchronizes each bit to SCLK).
 wire pattern_locked,pattern_lost_lock;wire[15:0]pattern_errors_gray;
 wire fca_locked,fca_lost,fcb_locked,fcb_lost;wire[13:0]fca_diff,fcb_diff;wire[15:0]fca_count,fcb_count;
 pt_toggle_div hd(host_rx_clk,core_rst_n,host_rx_div);
 pt_mgmt control(.rst_n(rst_n),.por_n(por_n),.sclk(host_sclk),.cs_n(host_cs_n),.mosi(host_mosi),.miso(host_miso),.miso_oe(host_miso_oe),
  .status(status),.enable(enable),.mode8(mode8),.rf_trim(rf_trim),.wire_trim(wire_trim),.clock_trim(clock_trim),
  .memory_write(memory_write),.memory_index(index),.memory_wdata(memory_wdata),.capture_data(capture_data),
  .capture_done(capture_done),.playback_enable(playback_enable),.capture_enable(capture_enable),
  .memory_loop(memory_loop),.memory_last(memory_last),
  .fault(fault),.island_pgood(island_pgood),.obs_status(obs_status),.wire_status(wire_status),
  .analog_cfg(analog_cfg),.debug_cfg(debug_cfg),.island_en(island_en),.island_on(island_on),
  .atb0_sw(atb0_sw),.atb1_sw(atb1_sw),.atb0_grp(atb0_grp),.atb1_grp(atb1_grp),.atb0_en(atb0_en),.atb1_en(atb1_en),.rx_en_aux(rx_en_aux),.rx_en_wclk(rx_en_wclk),.rx_en_wtx_ext(rx_en_wtx_ext),
  .clk_obs_oe(clk_obs_oe),.wclk_obs_oe(wclk_obs_oe),.dbg_obs0(dbg_obs0),.dbg_obs0_oe(dbg_obs0_oe),
  .dbg_obs1(dbg_obs1),.dbg_obs1_oe(dbg_obs1_oe),.wdbg_obs(wdbg_obs),.wdbg_obs_oe(wdbg_obs_oe),
  .commit_toggle(commit_toggle),.config_error(config_error),
  .pattern_locked(pattern_locked),.pattern_lost_lock(pattern_lost_lock),.pattern_errors_gray(pattern_errors_gray),
  .fca_locked(fca_locked),.fca_lost(fca_lost),.fca_diff(fca_diff),.fca_count(fca_count),
  .fcb_locked(fcb_locked),.fcb_lost(fcb_lost),.fcb_diff(fcb_diff),.fcb_count(fcb_count));
 // Frequency counters (rtl/pt_freq_count.sv, consolidation P3-7). status.pll_lock is reserved (reads 0).
 pt_freq_count fca(.rst_n(rst_n),.cfg_source(debug_cfg[`PT_D_DEBUG_FREQ_COUNT_A__SOURCE_LSB+:`PT_D_DEBUG_FREQ_COUNT_A__SOURCE_W]),
  .cfg_window(debug_cfg[`PT_D_DEBUG_FREQ_COUNT_A__WINDOW_LSB+:`PT_D_DEBUG_FREQ_COUNT_A__WINDOW_W]),
  .cfg_tol(debug_cfg[`PT_D_DEBUG_FREQ_COUNT_A__TOLERANCE_LSB+:`PT_D_DEBUG_FREQ_COUNT_A__TOLERANCE_W]),
  .cfg_count(debug_cfg[`PT_D_DEBUG_FREQ_COUNT_A__COUNT_LSB+:`PT_D_DEBUG_FREQ_COUNT_A__COUNT_W]),
  .cfg_target(debug_cfg[`PT_D_DEBUG_FREQ_COUNT_A__TARGET_LSB+:`PT_D_DEBUG_FREQ_COUNT_A__TARGET_W]),
  .src(fc_src),.ref_clk(ref_clk),.sclk(host_sclk),.locked_ref(),.locked(fca_locked),.lost_lock(fca_lost),.diff(fca_diff),.count(fca_count),
  .commit_toggle(commit_toggle));
 pt_freq_count fcb(.rst_n(rst_n),.cfg_source(debug_cfg[`PT_D_DEBUG_FREQ_COUNT_B__SOURCE_LSB+:`PT_D_DEBUG_FREQ_COUNT_B__SOURCE_W]),
  .cfg_window(debug_cfg[`PT_D_DEBUG_FREQ_COUNT_B__WINDOW_LSB+:`PT_D_DEBUG_FREQ_COUNT_B__WINDOW_W]),
  .cfg_tol(debug_cfg[`PT_D_DEBUG_FREQ_COUNT_B__TOLERANCE_LSB+:`PT_D_DEBUG_FREQ_COUNT_B__TOLERANCE_W]),
  .cfg_count(debug_cfg[`PT_D_DEBUG_FREQ_COUNT_B__COUNT_LSB+:`PT_D_DEBUG_FREQ_COUNT_B__COUNT_W]),
  .cfg_target(debug_cfg[`PT_D_DEBUG_FREQ_COUNT_B__TARGET_LSB+:`PT_D_DEBUG_FREQ_COUNT_B__TARGET_W]),
  .src(fc_src),.ref_clk(ref_clk),.sclk(host_sclk),.locked_ref(cdr_freq_locked),.locked(fcb_locked),.lost_lock(fcb_lost),.diff(fcb_diff),.count(fcb_count),
  .commit_toggle(commit_toggle));
 wire[39:0]stream_wire,prbs_word;wire stream_wire_valid,stream_wire_idle;
 wire[23:0]stream_rf;wire stream_rf_valid,stream_rf_mute;wire[15:0]core_status;
 // debug.pattern fields (spec/register-map.md 0x58-0x59). tx_mode 0 (payload) keeps the legacy
 // behaviour: wire_trim[15] alone selects the generator (PRBS31).
 wire[2:0]pat_tx_mode=debug_cfg[`PT_D_DEBUG_PATTERN__TX_MODE_LSB+:`PT_D_DEBUG_PATTERN__TX_MODE_W];
 wire[2:0]pat_check_mode=debug_cfg[`PT_D_DEBUG_PATTERN__CHECK_MODE_LSB+:`PT_D_DEBUG_PATTERN__CHECK_MODE_W];
 wire[2:0]pat_tx_eff=pat_tx_mode!=3'd0 ? pat_tx_mode : 3'd3;
 wire[2:0]pat_check_eff=pat_check_mode!=3'd0 ? pat_check_mode : pat_tx_eff;
 wire prbs_select=wire_trim[15]||pat_tx_mode!=3'd0;
 // SP-03 2x halfband TX interpolator (rtl/pt_interp2x.sv): with tx_interp = halfband the RF TX side of
 // the core (incl. bank playback) runs on rf_core_clk = rf_tx_clk / 2 (DAC at rf_tx_clk = 80 MHz);
 // with bypass (reset) rf_core_clk = rf_tx_clk and the samples pass straight through.
 wire wire_req_int,tx_enabled;reg prbs_ready;
 wire rf_core_clk,rf_tx_valid_core;wire[23:0]rf_tx_sample_core;
 wire[23:0]rf_tx_sample_i;wire rf_tx_valid_i;
 wire tx_halfband=analog_cfg[`PT_A_DIGITAL_TRANSPORT_CONFIG__TX_INTERP_LSB];
 pt_interp2x interp(.rst_n(rst_n),.clk_fast(rf_tx_clk),.halfband(tx_halfband),
  .core_clk(rf_core_clk),.in_sample(rf_tx_sample_core),.in_valid(rf_tx_valid_core),.out_sample(rf_tx_sample_i),.out_valid(rf_tx_valid_i));
 // RF TX output register (timing 2026-11-11, coordinator decision; interface row RF/assembly): the
 // DAC captures on the opposite rf_tx_clk edge, so rf_tx_sample / rf_tx_valid / rf_mute leave from
 // rising-edge rf_tx_clk flops. Bypass: a one-entry valid/ready output register keeps the port
 // handshake (a sample transfers on a clock with rf_tx_request && rf_tx_valid; an untaken sample is
 // held); the core sees request = (!o_v || rf_tx_request), so it delivers the next sample as the
 // held one leaves. Halfband: the interpolator stream is free-running (no request), the register is
 // a plain one-clock delay. Port latency +1 rf_tx_clk; the bus stays all-zero when nothing is valid.
 // DT-6 (coordinator 2026-11-11): forwarded DAC clock, built like the D2H forwarded clock: c_r toggles
 // on every rf_tx_clk rise, c_f copies it on the fall, rf_tx_clk_out = c_r ^ c_f (1 after a rise, 0
 // after a fall) leaves through the same kept mux2_2 output cell type as the data. The flops sit in the
 // same rf_tx_clk tree as the output register, so the macro's insertion delay cancels; the DAC captures
 // on the falling edge of rf_tx_clk_out (half a period after the data launch), skew budget in the SDC.
 reg rfc_r,rfc_f;
 always @(posedge rf_tx_clk or negedge rst_n)if(!rst_n)rfc_r<=1'b0;else rfc_r<=~rfc_r;
 always @(negedge rf_tx_clk or negedge rst_n)if(!rst_n)rfc_f<=1'b0;else rfc_f<=rfc_r;
 pt_out_mux rf_clk_out(.I0(rfc_r^rfc_f),.I1(1'b0),.S(1'b0),.Z(rf_tx_clk_out));
 wire rf_req_core;
 // cleared asynchronously by disable (as the core's valid is, through the RF reservoir reset)
 pt_rf_out_reg rf_out(.clk(rf_tx_clk),.rst_n(rst_n&&enable),.halfband(tx_halfband),.in_sample(rf_tx_sample_i),.in_valid(rf_tx_valid_i),
  .in_mute(cal_busy||stream_rf_mute),.req_core(rf_req_core),.sample(rf_tx_sample),.valid(rf_tx_valid),.mute(rf_mute),
  .request(rf_tx_request));
 // MEMORY v3 is the host-link fallback: with capture or playback selected (stopped-only, ENABLE=0
 // to change) the core leaves the host-link reset (core_rst_n needs the host word clock) and uses
 // RESET_N; every core domain still releases through its own synchronized ENABLE.
 wire core_reset_n=(capture_enable||playback_enable)?rst_n:core_rst_n;
 pt_core core(core_reset_n,enable,mode8,host_tx_clk,wire_rx_clk,wire_tx_clk,rf_rx_clk,rf_core_clk,
 h2d_quad,d2h_quad,wire_rx_data,wire_rx_valid,stream_wire,stream_wire_valid,wire_tx_request,
 rf_rx_sample,rf_rx_valid,stream_rf,stream_rf_valid,rf_req_core,core_status,stream_wire_idle,stream_rf_mute,
 analog_cfg[`PT_A_DIGITAL_TRANSPORT_CONFIG__PAYLOAD_IQ_LSB],linecode,rx_gain,rx_gain_active,
 // MEMORY v3 (sharing S1): capture/playback in the transport banks; pt_memory is deleted.
 capture_enable,playback_enable,memory_loop,memory_last,host_sclk,memory_write,index,memory_wdata,capture_data,capture_done,
 prbs_select,prbs_word,tx_enabled&&prbs_ready,!tx_enabled,wire_req_int);
 pt_sync_bit e(wire_tx_clk,rst_n,enable,tx_enabled);
 // Shared wired pattern generator/checker (rtl/pt_pattern.sv, consolidation P2-6): 40-bit cores directly
 // on the 40-bit quad clocks (AC-1 S3: no gearbox, no clock gate). CDC: the quasi-static
 // debug.pattern fields (change only by commit while ENABLE=0, when the generator is in reset and the
 // checker disabled) pass through 2-flop synchronizers per bit; inject and check_clear are live levels,
 // synchronized and edge-detected (one error / one clear per 0->1 transition).
 wire[13:0]pat_tx_cfg;wire pat_inj_s;reg pat_inj_d;
 pt_sync_vec #(14) ptxc(wire_tx_clk,rst_n,{pat_tx_eff,debug_cfg[`PT_D_DEBUG_PATTERN__TX_INVERT_LSB],
  debug_cfg[`PT_D_DEBUG_PATTERN__USER_WORD_LSB+:`PT_D_DEBUG_PATTERN__USER_WORD_W]},pat_tx_cfg);
 pt_sync_bit ptxi(wire_tx_clk,rst_n,debug_cfg[`PT_D_DEBUG_PATTERN__INJECT_LSB],pat_inj_s);
 always @(posedge wire_tx_clk or negedge rst_n)if(!rst_n)pat_inj_d<=0;else pat_inj_d<=pat_inj_s;
 // The generator's word is a register; it loads on the first clock after reset (ready the clock after)
 // and advances on every clock where the consumer takes it (wire_tx_request with prbs_select).
 wire prbs_rst_n=rst_n&&tx_enabled;
 always @(posedge wire_tx_clk or negedge prbs_rst_n)if(!prbs_rst_n)prbs_ready<=0;else prbs_ready<=1;
 pt_pattern_gen #(.W(40)) prbs(.clk(wire_tx_clk),.rst_n(prbs_rst_n),.ce(1'b1),.step(wire_req_int&&prbs_select&&prbs_ready),
  .cfg_mode(pat_tx_cfg[13:11]),.cfg_invert(pat_tx_cfg[10]),.cfg_user({4{pat_tx_cfg[9:0]}}),.data_in(40'd0),
  .inject(pat_inj_s&&!pat_inj_d),.word(prbs_word));
 wire rx_check_en,pat_clr_s;reg pat_clr_d;wire[3:0]pat_rx_cfg;wire[15:0]prbs_errors;
 pt_sync_bit rxc(wire_rx_clk,rst_n,enable&&(wire_trim[15]||debug_cfg[`PT_D_DEBUG_PATTERN__CHECK_ENABLE_LSB]),rx_check_en);
 pt_sync_vec #(4) prxc(wire_rx_clk,rst_n,{pat_check_eff,debug_cfg[`PT_D_DEBUG_PATTERN__CHECK_INVERT_LSB]},pat_rx_cfg);
 pt_sync_bit prxl(wire_rx_clk,rst_n,debug_cfg[`PT_D_DEBUG_PATTERN__CHECK_CLEAR_LSB],pat_clr_s);
 always @(posedge wire_rx_clk or negedge rst_n)if(!rst_n)pat_clr_d<=0;else pat_clr_d<=pat_clr_s;
 pt_pattern_check #(.W(40),.CW(16)) prbs_check(.clk(wire_rx_clk),.rst_n(rst_n),.ce(1'b1),.enable(rx_check_en),.valid(wire_rx_valid),
  .data(wire_rx_data),.cfg_mode(pat_rx_cfg[3:1]),.cfg_invert(pat_rx_cfg[0]),.clear(!rx_check_en||(pat_clr_s&&!pat_clr_d)),
  .locked(pattern_locked),.lost_lock(pattern_lost_lock),.errors(prbs_errors),.errors_gray(pattern_errors_gray));
 // The pattern word shares the core's wire lane registers (falling-edge low half, rising-edge high
 // half), so wire_tx_data always leaves from the same launch flops (ff-corner hold, AC1_R4 -0.34 ns).
 assign wire_tx_data=stream_wire;
 // The core's wired output stage (lane_q / valid / idle registers, valid/ready) serves both the stream
 // and the pattern word (timing 2026-11-11); the generator steps when the stage takes its word.
 assign wire_tx_valid=stream_wire_valid;
 assign wire_idle=stream_wire_idle;
 // The DAC data bus is held static (all zero) whenever no sample is valid, e.g. throughout
 // receive-only operation, so idle DAC inputs do not toggle next to the receive path.
 assign rf_tx_valid_core=stream_rf_valid;
 assign rf_tx_sample_core=rf_tx_valid_core?stream_rf:24'd0;
 // pt_calibrator (ref-trim SAR) removed (FPGA offload audit, D11: no on-chip sequencer; no analog
 // consumer of calibration_trial / calibration_above_target). The ports stay until integration drops
 // them (interface-changes.md); cal_busy / cal_done read 0.
 assign calibration_trial=12'd0;assign cal_busy=1'b0;assign cal_done=1'b0;

 assign status=core_status|{cal_done,cal_busy,capture_done,13'b0};
endmodule

// RF TX output register (see pt_digital): bypass = one-entry valid/ready register (port transfer on
// request && valid, an untaken sample is held, the producer sees req_core = !valid || request);
// halfband = plain one-clock delay of the free-running interpolator stream. mute is loaded with the
// sample (= !valid || mute command for that sample, as the core's); while a sample is held untaken the
// mute level is held too (independent review 2026-11-11).
module pt_rf_out_reg(input wire clk,rst_n,halfband,input wire[23:0]in_sample,input wire in_valid,in_mute,
 output wire req_core,output reg[23:0]sample,output reg valid,mute,input wire request);
 assign req_core=halfband?request:(!valid||request);
 wire load=halfband||!valid||request;
 always @(posedge clk or negedge rst_n)
  if(!rst_n)begin sample<=24'd0;valid<=1'b0;mute<=1'b1;end
  else begin
   if(load)begin sample<=in_sample;valid<=in_valid;mute<=in_mute;end   // mute stays aligned with the held sample
  end
endmodule

// Divide-by-two toggle used only as a DBG_OBS liveness indicator for a clock domain.
module pt_toggle_div(input wire clk,rst_n,output reg q);
 always @(posedge clk or negedge rst_n)if(!rst_n)q<=0;else q<=!q;
endmodule
