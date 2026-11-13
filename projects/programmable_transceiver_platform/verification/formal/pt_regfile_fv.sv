// Formal harness for the generated register file. Every input is unconstrained on
// every SCLK edge (any write to any address with any data, any status, power-good
// and fault pattern), which over-approximates the 32-clock SPI framing. The proof
// starts in reset; rst_n may be asserted again at any time. The safety properties
// themselves are generated into rtl/pt_regfile.sv under `ifdef FORMAL.
module pt_regfile_fv(input wire rst_n,por_n,por_bypass,sclk,wr_en,input wire[7:0]wr_addr,input wire[15:0]wr_data,
 input wire[7:0]rd_addr,input wire[15:0]status,input wire[23:0]capture_data,input wire capture_done,
 input wire fault,input wire[5:0]island_pgood,input wire[31:0]obs_status,input wire[15:0]wire_status,
 input wire pattern_locked,pattern_lost_lock,input wire[15:0]pattern_errors_gray,
 input wire fca_locked,fca_lost,fcb_locked,fcb_lost,input wire[13:0]fca_diff,fcb_diff,input wire[15:0]fca_count,fcb_count);
 // rst_n = RESET_N AND (por_n OR por_bypass): with the G3 strap high, POR does NOT imply the combined
 // reset (por_n may be low, even stuck low, while rst_n is high), so por_n is left free after the
 // initial reset: every property below is proven for both strap levels.
 initial assume(!rst_n&&!por_n);
 pt_regfile dut(.rst_n(rst_n),.por_n(por_n),.por_bypass(por_bypass),.sclk(sclk),.wr_en(wr_en),.wr_addr(wr_addr),.wr_data(wr_data),.rd_addr(rd_addr),
  .rd_data(),.rd_hi(7'd0),.rd_data0(),.rd_data1(),.status(status),.enable(),.mode8(),.rf_trim(),.wire_trim(),.clock_trim(),.memory_write(),
  .memory_index(),.memory_wdata(),.capture_data(capture_data),.capture_done(capture_done),.playback_enable(),
  .capture_enable(),.fault(fault),.island_pgood(island_pgood),.obs_status(obs_status),.wire_status(wire_status),
  .analog_cfg(),.debug_cfg(),.island_en(),.island_on(),.atb0_sw(),.atb1_sw(),.rx_en_aux(),.rx_en_wclk(),
  .rx_en_wtx_ext(),.clk_obs_oe(),.wclk_obs_oe(),.dbg_obs0(),.dbg_obs0_oe(),.dbg_obs1(),.dbg_obs1_oe(),
  .wdbg_obs(),.wdbg_obs_oe(),.commit_toggle(),.config_error(),
  .pattern_locked(pattern_locked),.pattern_lost_lock(pattern_lost_lock),.pattern_errors_gray(pattern_errors_gray),
  .fca_locked(fca_locked),.fca_lost(fca_lost),.fca_diff(fca_diff),.fca_count(fca_count),
  .fcb_locked(fcb_locked),.fcb_lost(fcb_lost),.fcb_diff(fcb_diff),.fcb_count(fcb_count));
endmodule
