// Macro-level SPI testbench for pt_digital_macro, used on both the RTL and the post-route
// gate-level netlist (verification/digital_hardening/gls.sh). It executes the command stream of
// verification/check_regfile.py (same op codes as sim/tb_regfile.sv) through the macro's real
// SPI/reset pins and logs every SPI read and, at each snapshot, every macro output.
// Differences from tb_regfile: reset is applied on the macro's two reset inputs (op 3 = RESET_N
// pad only, op 6 = POR only, R0 = both), the status inputs come from the real datapath (fast
// clocks are held stopped), and op 7 (checker status) has no external pin here (no-op).
// The final directed section (ops 8/9) drives the analog status inputs and fast clocks.
// With PT_LOOPBACK the D2H pins (data and forwarded clock) drive the H2D pins: the transport's own
// D2H frames come back through the DDR/SDR capture, FIFO and frame receiver (core status `locked`).
`timescale 1ns/1ps
`include "pt_regmap_defs.svh"
module tb_digital_gl;
 reg reset_n_pad=1,por_n=1,sclk=0,cs_n=0,mosi=0,fault=0;
 reg[5:0]pgood=0;reg[11:0]astat=0;reg[12:0]wstat=0;
 reg fclk=0;reg run_clk=0;
 supply1 vdd;supply0 vss;
 wire gclk=fclk&run_clk;
 wire spi_miso,spi_miso_oe,d2h_clk_pin,d2h_oe,d2h_sl,wire_tx_valid,wire_idle,rf_tx_valid,rf_mute,enable,mode8;
 wire[9:0]d2h_pin;wire[19:0]wire_tx_data;wire[1:0]d2h_pdrv;wire[23:0]rf_tx_sample;wire[15:0]rf_trim,wire_trim,clock_trim;
 wire[11:0]calibration_trial;
 wire[`PT_ANALOG_CFG_W-1:0]analog_cfg;wire[`PT_DEBUG_CFG_W-1:0]debug_cfg;
 wire[`PT_ISLAND_W-1:0]island_en,island_on;wire[`PT_ATB0_GRP_W-1:0]atb0_grp;wire[`PT_ATB1_GRP_W-1:0]atb1_grp;wire atb0_en,atb1_en;wire[`PT_ATB_W-1:0]atb0_sw,atb1_sw;
 wire rx_en_aux,rx_en_wclk,rx_en_wtx_ext,clk_obs_oe,wclk_obs_oe;
 wire dbg_obs0,dbg_obs0_oe,dbg_obs1,dbg_obs1_oe,wdbg_obs,wdbg_obs_oe,commit_toggle;
 wire ct_word_clk,ct_word_load,ct_ser_run,ct_bit_phase,ct_qualified,ct_armed,ct_marker_seen,ct_launched,ct_arm_fault,ct_det_clk;
 wire[2:0]ct_det_div;
 pt_digital_macro dut(
`ifdef USE_POWER_PINS
  .VDD(vdd),.VSS(vss),
`endif
  .reset_n_pad(reset_n_pad),.por_n(por_n),.spi_sclk(sclk),.spi_cs_n(cs_n),.spi_mosi(mosi),
  .spi_miso(spi_miso),.spi_miso_oe(spi_miso_oe),.host_word_clk(gclk),
`ifdef PT_LOOPBACK
  .h2d_clk(d2h_clk_pin),.h2d_pin(d2h_pin),   // D2H pins looped to H2D pins (host-link test)
`else
  .h2d_clk(gclk),.h2d_pin(10'h155),
`endif
  .d2h_pin(d2h_pin),.d2h_clk_pin(d2h_clk_pin),.d2h_oe(d2h_oe),.d2h_pdrv(d2h_pdrv),.d2h_sl(d2h_sl),
  .ref_clk(gclk),.wire_rx_clk(gclk),.wire_tx_clk(gclk),.rf_rx_clk(gclk),.rf_tx_clk(gclk),
  .wire_rx_data(20'h0),.wire_rx_valid(1'b0),.wire_tx_data(wire_tx_data),.wire_tx_valid(wire_tx_valid),
  .wire_idle(wire_idle),.wire_tx_request(1'b0),.rf_rx_sample(24'h0),.rf_rx_valid(1'b0),.rf_tx_sample(rf_tx_sample),
  .rf_tx_valid(rf_tx_valid),.rf_mute(rf_mute),.rf_tx_request(1'b0),.enable(enable),.mode8(mode8),.rf_trim(rf_trim),
  .wire_trim(wire_trim),.clock_trim(clock_trim),.calibration_above_target(1'b0),.calibration_trial(calibration_trial),
  .fault(fault),.island_pgood(pgood),.analog_status(astat),.wire_analog_status(wstat),.analog_cfg(analog_cfg),
  .debug_cfg(debug_cfg),.island_en(island_en),.island_on(island_on),.atb0_grp(atb0_grp),.atb1_grp(atb1_grp),.atb0_en(atb0_en),.atb1_en(atb1_en),.atb0_sw(atb0_sw),.atb1_sw(atb1_sw),.rx_en_aux(rx_en_aux),
  .rx_en_wclk(rx_en_wclk),.rx_en_wtx_ext(rx_en_wtx_ext),.clk_obs_oe(clk_obs_oe),.wclk_obs_oe(wclk_obs_oe),
  .dbg_obs0(dbg_obs0),.dbg_obs0_oe(dbg_obs0_oe),.dbg_obs1(dbg_obs1),.dbg_obs1_oe(dbg_obs1_oe),.wdbg_obs(wdbg_obs),
  .wdbg_obs_oe(wdbg_obs_oe),.commit_toggle(commit_toggle),
  .ct_wclk(gclk),.ct_ref_clk(1'b0),.ct_det_clk_in(gclk),.ct_pll_lock(1'b0),.ct_marker(1'b0),
  .ct_cfg_det_en(1'b0),.ct_cfg_det_div(3'd0),.fc_src({6{gclk}}),.cdr_freq_locked(),
  .ct_word_clk(ct_word_clk),.ct_word_load(ct_word_load),.ct_ser_run(ct_ser_run),.ct_bit_phase(ct_bit_phase),
  .ct_qualified(ct_qualified),.ct_armed(ct_armed),.ct_marker_seen(ct_marker_seen),.ct_launched(ct_launched),
  .ct_arm_fault(ct_arm_fault),.ct_det_div(ct_det_div),.ct_det_clk(ct_det_clk));
 always #10 fclk=~fclk;  // 50 MHz shared fast clock, gated by run_clk (directed section only)

 integer fd,log,code,op,a,b,c,i,ncmd;
 reg[15:0]rd;reg[31:0]frame;
 task spi(input[7:0]cmd,input[7:0]addr,input[15:0]data,output[15:0]q);
  begin
   frame={cmd,addr,data};q=0;cs_n=0;#50;
   for(i=31;i>=0;i=i-1)begin
    mosi=frame[i];#50;sclk=1;if(i<16)q[i]=spi_miso;#50;sclk=0;
   end
   #50;cs_n=1;mosi=0;#100;
  end
 endtask
 // Snapshot: regfile-visible fields first (same order as tb_regfile where the field is a macro
 // output), then every remaining macro output.
 task snap(input[8*4-1:0]tag);
  $fdisplay(log,"S %0s %h %h %h %h %h %b%b%b%b%b %b%b%b%b%b%b %b %h %h %b %b | %h %h %h %h %b %b %b %b %h %h %b %b %b %h %b%b%b%b%b%b%b%b%b%b %h %h %h",
   tag,analog_cfg,debug_cfg,island_en,atb0_sw,atb1_sw,rx_en_aux,rx_en_wclk,rx_en_wtx_ext,clk_obs_oe,wclk_obs_oe,
   dbg_obs0,dbg_obs0_oe,dbg_obs1,dbg_obs1_oe,wdbg_obs,wdbg_obs_oe,commit_toggle,{7'b0,enable},{7'b0,mode8},spi_miso_oe,spi_miso,
   rf_trim,wire_trim,clock_trim,calibration_trial,wire_tx_valid,wire_idle,rf_tx_valid,rf_mute,wire_tx_data,rf_tx_sample,
   d2h_oe,d2h_clk_pin,d2h_sl,{d2h_pdrv,d2h_pin},
   ct_word_clk,ct_word_load,ct_ser_run,ct_bit_phase,ct_qualified,ct_armed,ct_marker_seen,ct_launched,ct_arm_fault,ct_det_clk,
   ct_det_div,island_on,{atb1_grp,atb0_grp,atb1_en,atb0_en});
 endtask
 initial begin
  fd=$fopen("commands.txt","r");log=$fopen("tb.log","w");
  if(fd==0)begin $display("FATAL no commands.txt");$finish;end
  #5;cs_n=1;#5;reset_n_pad=0;por_n=0;#90;snap("R0");por_n=1;reset_n_pad=1;#100;ncmd=0;
  while(!$feof(fd))begin
   code=$fscanf(fd,"%d %h %h %h\n",op,a,b,c);
   if(code==4)begin
    ncmd=ncmd+1;
    case(op)
     0:spi(8'h80,a[7:0],b[15:0],rd);
     1:begin spi(8'h00,a[7:0],16'h0,rd);$fdisplay(log,"R %h %h",a[7:0],rd);end
     2:begin pgood=a[5:0];fault=b[0];#20;end
     3:begin reset_n_pad=0;#30;snap("RST");#30;reset_n_pad=1;#100;end
     4:snap("SNAP");
     5:begin
       frame={8'h80,a[7:0],b[15:0]};cs_n=0;#50;
       for(i=31;i>=16;i=i-1)begin mosi=frame[i];#50;sclk=1;#50;sclk=0;end
       #20;reset_n_pad=0;#30;snap("MID");#30;cs_n=1;mosi=0;#50;reset_n_pad=1;#100;
      end
     6:begin por_n=0;#30;snap("POR");#30;por_n=1;#100;end
     7:begin end
     8:begin astat=a[11:0];wstat=b[12:0];#20;end                 // analog status inputs
     9:begin run_clk=a[0];#(1000*b+20);end                         // gate fast clocks, run b us
     default:begin $display("FATAL bad op %0d",op);$finish;end
    endcase
   end
  end
  $fdisplay(log,"E %0d",ncmd);$fclose(log);$display("tb_digital_gl done: %0d commands",ncmd);$finish;
 end
endmodule
