`include "pt_regmap_defs.svh"
module pt_digital #(parameter STREAM_V2=1)(input wire rst_n,ref_clk,
 input wire host_sclk,host_cs_n,host_mosi,output wire host_miso,host_miso_oe,
 input wire host_tx_clk,host_rx_clk,wire_rx_clk,wire_tx_clk,rf_rx_clk,rf_tx_clk,
 input wire[9:0]h2d_word,output wire[9:0]d2h_word,
 // Wired boundary (consolidation P3-6): 20-bit double words, word 0 (earlier on the line) in [9:0],
 // one double word per wire_tx_clk / wire_rx_clk edge (<= 125 MHz). valid/request are per double word.
 input wire[19:0]wire_rx_data,input wire wire_rx_valid,output wire[19:0]wire_tx_data,
 output wire wire_tx_valid,wire_idle,input wire wire_tx_request,
 input wire[23:0]rf_rx_sample,input wire rf_rx_valid,output wire[23:0]rf_tx_sample,
 output wire rf_tx_valid,rf_mute,input wire rf_tx_request,
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
 output wire dbg_obs0,dbg_obs0_oe,dbg_obs1,dbg_obs1_oe,wdbg_obs,wdbg_obs_oe,commit_toggle);
 wire memory_write,capture_done,playback_enable,capture_enable;wire[4:0]index;wire[23:0]memory_wdata,capture_data;
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
 pt_toggle_div hd(host_rx_clk,rst_n,host_rx_div);
 pt_mgmt control(.rst_n(rst_n),.por_n(por_n),.sclk(host_sclk),.cs_n(host_cs_n),.mosi(host_mosi),.miso(host_miso),.miso_oe(host_miso_oe),
  .status(status),.enable(enable),.mode8(mode8),.rf_trim(rf_trim),.wire_trim(wire_trim),.clock_trim(clock_trim),
  .memory_write(memory_write),.memory_index(index),.memory_wdata(memory_wdata),.capture_data(capture_data),
  .capture_done(capture_done),.playback_enable(playback_enable),.capture_enable(capture_enable),
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
  .src(fc_src),.ref_clk(ref_clk),.sclk(host_sclk),.locked_ref(),.locked(fca_locked),.lost_lock(fca_lost),.diff(fca_diff),.count(fca_count));
 pt_freq_count fcb(.rst_n(rst_n),.cfg_source(debug_cfg[`PT_D_DEBUG_FREQ_COUNT_B__SOURCE_LSB+:`PT_D_DEBUG_FREQ_COUNT_B__SOURCE_W]),
  .cfg_window(debug_cfg[`PT_D_DEBUG_FREQ_COUNT_B__WINDOW_LSB+:`PT_D_DEBUG_FREQ_COUNT_B__WINDOW_W]),
  .cfg_tol(debug_cfg[`PT_D_DEBUG_FREQ_COUNT_B__TOLERANCE_LSB+:`PT_D_DEBUG_FREQ_COUNT_B__TOLERANCE_W]),
  .cfg_count(debug_cfg[`PT_D_DEBUG_FREQ_COUNT_B__COUNT_LSB+:`PT_D_DEBUG_FREQ_COUNT_B__COUNT_W]),
  .cfg_target(debug_cfg[`PT_D_DEBUG_FREQ_COUNT_B__TARGET_LSB+:`PT_D_DEBUG_FREQ_COUNT_B__TARGET_W]),
  .src(fc_src),.ref_clk(ref_clk),.sclk(host_sclk),.locked_ref(cdr_freq_locked),.locked(fcb_locked),.lost_lock(fcb_lost),.diff(fcb_diff),.count(fcb_count));
 wire[19:0]stream_wire,prbs_word;wire stream_wire_valid,stream_wire_idle;
 wire[23:0]stream_rf,play_rf;wire stream_rf_valid,stream_rf_mute,play_valid;wire[15:0]core_status;
 // debug.pattern fields (spec/register-map.md 0x58-0x59). tx_mode 0 (payload) keeps the legacy
 // behaviour: wire_trim[15] alone selects the generator (PRBS31).
 wire[2:0]pat_tx_mode=debug_cfg[`PT_D_DEBUG_PATTERN__TX_MODE_LSB+:`PT_D_DEBUG_PATTERN__TX_MODE_W];
 wire[2:0]pat_check_mode=debug_cfg[`PT_D_DEBUG_PATTERN__CHECK_MODE_LSB+:`PT_D_DEBUG_PATTERN__CHECK_MODE_W];
 wire[2:0]pat_tx_eff=pat_tx_mode!=3'd0 ? pat_tx_mode : 3'd3;
 wire[2:0]pat_check_eff=pat_check_mode!=3'd0 ? pat_check_mode : pat_tx_eff;
 wire prbs_select=wire_trim[15]||pat_tx_mode!=3'd0,play_select=playback_enable;
 pt_core #(.STREAM_V2(STREAM_V2)) core(rst_n,enable,mode8,host_tx_clk,host_rx_clk,wire_rx_clk,wire_tx_clk,rf_rx_clk,rf_tx_clk,
 h2d_word,d2h_word,wire_rx_data,wire_rx_valid,stream_wire,stream_wire_valid,wire_tx_request&&!prbs_select,
 rf_rx_sample,rf_rx_valid,stream_rf,stream_rf_valid,rf_tx_request&&!play_select,core_status,stream_wire_idle,stream_rf_mute);
 pt_memory memory(rst_n,host_sclk,memory_write,index,memory_wdata,capture_data,rf_rx_clk,rf_tx_clk,
 capture_enable&&enable,playback_enable&&enable,rf_rx_sample,rf_rx_valid,capture_done,play_rf,play_valid,rf_tx_request);
 wire tx_enabled;pt_sync_bit e(wire_tx_clk,rst_n,enable,tx_enabled);
 // Shared wired pattern generator/checker (rtl/pt_pattern.sv, consolidation P2-6): 20-bit cores directly
 // on the 20-bit double-word clocks (P3-6: no 10<->20 gearbox, no clock gate). CDC: the quasi-static
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
 reg prbs_ready;wire prbs_rst_n=rst_n&&tx_enabled;
 always @(posedge wire_tx_clk or negedge prbs_rst_n)if(!prbs_rst_n)prbs_ready<=0;else prbs_ready<=1;
 pt_pattern_gen #(.W(20)) prbs(.clk(wire_tx_clk),.rst_n(prbs_rst_n),.ce(1'b1),.step(wire_tx_request&&prbs_select&&prbs_ready),
  .cfg_mode(pat_tx_cfg[13:11]),.cfg_invert(pat_tx_cfg[10]),.cfg_user({pat_tx_cfg[9:0],pat_tx_cfg[9:0]}),.data_in(20'd0),
  .inject(pat_inj_s&&!pat_inj_d),.word(prbs_word));
 wire rx_check_en,pat_clr_s;reg pat_clr_d;wire[3:0]pat_rx_cfg;wire[15:0]prbs_errors;
 pt_sync_bit rxc(wire_rx_clk,rst_n,enable&&(wire_trim[15]||debug_cfg[`PT_D_DEBUG_PATTERN__CHECK_ENABLE_LSB]),rx_check_en);
 pt_sync_vec #(4) prxc(wire_rx_clk,rst_n,{pat_check_eff,debug_cfg[`PT_D_DEBUG_PATTERN__CHECK_INVERT_LSB]},pat_rx_cfg);
 pt_sync_bit prxl(wire_rx_clk,rst_n,debug_cfg[`PT_D_DEBUG_PATTERN__CHECK_CLEAR_LSB],pat_clr_s);
 always @(posedge wire_rx_clk or negedge rst_n)if(!rst_n)pat_clr_d<=0;else pat_clr_d<=pat_clr_s;
 pt_pattern_check #(.W(20),.CW(16)) prbs_check(.clk(wire_rx_clk),.rst_n(rst_n),.ce(1'b1),.enable(rx_check_en),.valid(wire_rx_valid),
  .data(wire_rx_data),.cfg_mode(pat_rx_cfg[3:1]),.cfg_invert(pat_rx_cfg[0]),.clear(!rx_check_en||(pat_clr_s&&!pat_clr_d)),
  .locked(pattern_locked),.lost_lock(pattern_lost_lock),.errors(prbs_errors),.errors_gray(pattern_errors_gray));
 assign wire_tx_data=prbs_select?prbs_word:stream_wire;
 assign wire_tx_valid=prbs_select?tx_enabled&&prbs_ready:stream_wire_valid;
 assign wire_idle=prbs_select?!tx_enabled:stream_wire_idle;
 assign rf_tx_sample=play_select?play_rf:stream_rf;
 assign rf_tx_valid=play_select?play_valid:stream_rf_valid;
 wire cal_start;
 pt_sync_bit cs(ref_clk,rst_n,clock_trim[15]&&!enable,cal_start);
 pt_calibrator calibration(ref_clk,rst_n,cal_start,calibration_above_target,calibration_trial,cal_busy,cal_done);
 assign rf_mute=cal_busy||(play_select?!play_valid:stream_rf_mute);
 assign status=core_status|{cal_done,cal_busy,capture_done,13'b0};
endmodule

// Divide-by-two toggle used only as a DBG_OBS liveness indicator for a clock domain.
module pt_toggle_div(input wire clk,rst_n,output reg q);
 always @(posedge clk or negedge rst_n)if(!rst_n)q<=0;else q<=!q;
endmodule
