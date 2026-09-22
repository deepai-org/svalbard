module pt_digital #(parameter STREAM_V2=1)(input wire rst_n,ref_clk,
 input wire host_sclk,host_cs_n,host_mosi,output wire host_miso,host_miso_oe,
 input wire host_tx_clk,host_rx_clk,wire_rx_clk,wire_tx_clk,rf_rx_clk,rf_tx_clk,
 input wire[9:0]h2d_word,output wire[9:0]d2h_word,
 input wire[9:0]wire_rx_data,input wire wire_rx_valid,output wire[9:0]wire_tx_data,
 output wire wire_tx_valid,wire_idle,input wire wire_tx_request,
 input wire[23:0]rf_rx_sample,input wire rf_rx_valid,output wire[23:0]rf_tx_sample,
 output wire rf_tx_valid,rf_mute,input wire rf_tx_request,
 output wire enable,mode8,output wire[15:0]rf_trim,wire_trim,clock_trim,
 input wire calibration_above_target,output wire[11:0]calibration_trial,
 output wire[15:0]status);
 wire memory_write,capture_done,playback_enable,capture_enable;wire[4:0]index;wire[23:0]memory_wdata,capture_data;
 pt_control control(rst_n,host_sclk,host_cs_n,host_mosi,host_miso,host_miso_oe,status,enable,mode8,
 rf_trim,wire_trim,clock_trim,memory_write,index,memory_wdata,capture_data,capture_done,playback_enable,capture_enable);
 wire[9:0]stream_wire,prbs_word;wire stream_wire_valid,stream_wire_idle;
 wire[23:0]stream_rf,play_rf;wire stream_rf_valid,stream_rf_mute,play_valid;wire[15:0]core_status;
 wire prbs_select=wire_trim[15],play_select=playback_enable;
 pt_core #(.STREAM_V2(STREAM_V2)) core(rst_n,enable,mode8,host_tx_clk,host_rx_clk,wire_rx_clk,wire_tx_clk,rf_rx_clk,rf_tx_clk,
 h2d_word,d2h_word,wire_rx_data,wire_rx_valid,stream_wire,stream_wire_valid,wire_tx_request&&!prbs_select,
 rf_rx_sample,rf_rx_valid,stream_rf,stream_rf_valid,rf_tx_request&&!play_select,core_status,stream_wire_idle,stream_rf_mute);
 pt_memory memory(rst_n,host_sclk,memory_write,index,memory_wdata,capture_data,rf_rx_clk,rf_tx_clk,
 capture_enable&&enable,playback_enable&&enable,rf_rx_sample,rf_rx_valid,capture_done,play_rf,play_valid,rf_tx_request);
 wire tx_enabled;pt_sync_bit e(wire_tx_clk,rst_n,enable,tx_enabled);
 pt_prbs prbs(wire_tx_clk,rst_n&&tx_enabled,wire_tx_request&&prbs_select,prbs_word);
 assign wire_tx_data=prbs_select?prbs_word:stream_wire;
 assign wire_tx_valid=prbs_select?tx_enabled:stream_wire_valid;
 assign wire_idle=prbs_select?!tx_enabled:stream_wire_idle;
 assign rf_tx_sample=play_select?play_rf:stream_rf;
 assign rf_tx_valid=play_select?play_valid:stream_rf_valid;
 wire cal_start,cal_busy,cal_done;
 pt_sync_bit cs(ref_clk,rst_n,clock_trim[15]&&!enable,cal_start);
 pt_calibrator calibration(ref_clk,rst_n,cal_start,calibration_above_target,calibration_trial,cal_busy,cal_done);
 assign rf_mute=cal_busy||(play_select?!play_valid:stream_rf_mute);
 assign status=core_status|{cal_done,cal_busy,capture_done,13'b0};
endmodule
