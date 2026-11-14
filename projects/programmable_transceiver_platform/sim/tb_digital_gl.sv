// Macro-level SPI testbench for pt_digital_macro, used on both the RTL and the post-route
// gate-level netlist (verification/digital_hardening/gls.sh). It executes the command stream of
// verification/check_regfile.py (same op codes as sim/tb_regfile.sv) through the macro's real
// SPI/reset pins and logs every SPI read and, at each snapshot, EVERY macro output (r7: the port list comes from
// verification/digital_hardening/gls_ports.py -> tb_gl_ports.svh, so the bench follows the macro boundary).
// Differences from tb_regfile: reset is applied on the macro's two reset inputs (op 3 = RESET_N
// pad only, op 6 = POR only, R0 = both), the status inputs come from the real datapath (fast
// clocks are held stopped), and op 7 (checker status) has no external pin here (no-op).
// op 2: a[5:0] = island power-good by enable group (0 wired, 1 rf, 2 pll, 4 conv, 5 debug; bit 3 has no switch),
// applied to every switch of the group; b[0] = the external fault pin.
// The final directed section (ops 8/9) drives the analog status inputs and fast clocks.
// With PT_LOOPBACK the D2H pins (data and forwarded clock) drive the H2D pins: the transport's own
// D2H frames come back through the DDR/SDR capture, FIFO and frame receiver (core status `locked`).
`timescale 1ns/1ps
`include "pt_regmap_defs.svh"
module tb_digital_gl;
 reg reset_n_pad=1,por_n=1,sclk=0,cs_n=0,mosi=0,fault=0;
 reg[5:0]pgood=0;reg[20:0]sstat=0;
 reg fclk=0;reg run_clk=0;
 supply1 vdd;supply0 vss;
 wire gclk=fclk&run_clk;
`include "tb_gl_ports.svh"
 // Loopback FPGA model: the DDR forwarded D2H clock is edge-aligned (transport rework 2026-11-10), so
 // the looped clock is centred with a quarter host-DDR-clock delay (5 ns at the 50 MHz bench clock),
 // as the FPGA's input delay would; the SDR clock (reduced rates) is mid-word already and tolerates it.
 wire #5 d2h_clk_lb = o_d2h_clk_pin;
 pt_digital_macro dut(
`ifdef USE_POWER_PINS
  .VDD(vdd),.VSS(vss),
`endif
  .reset_n_pad(reset_n_pad),.por_n(por_n),.spi_sclk(sclk),.spi_cs_n(cs_n),.spi_mosi(mosi),.host_word_clk(gclk),
`ifdef PT_LOOPBACK
  .h2d_clk(d2h_clk_lb),.h2d_pin(o_d2h_pin),    // D2H pins looped to H2D pins (host-link test)
`else
  .h2d_clk(gclk),.h2d_pin(10'h155),
`endif
  .ref_clk(gclk),.wire_rx_clk(gclk),.wire_tx_clk(gclk),.rf_rx_clk(gclk),.rf_tx_clk(gclk),.ct_wclk(gclk),.fc_src({6{gclk}}),
  .fault(fault),
  .s_pg_wired_rx(pgood[0]),.s_pg_wired_cap(pgood[0]),.s_pg_wired_tx(pgood[0]),
  .s_pg_rf_rx(pgood[1]),.s_pg_rf_tx(pgood[1]),.s_pg_lod(pgood[1]),.s_pg_lo(pgood[1]),
  .s_pg_pll(pgood[2]),.s_pg_conv(pgood[4]),.s_pg_debug(pgood[5]),
  .s_pll_tx_lock(sstat[0]),.s_pll_cdr_lock(sstat[1]),.s_ref_present(sstat[2]),.s_refbuf_ready(sstat[3]),
  .s_adc_i_ovl(sstat[4]),.s_adc_i_b_ovl(sstat[5]),.s_adc_q_ovl(sstat[6]),.s_adc_q_b_ovl(sstat[7]),
  .s_adc_i_done(sstat[8]),.s_adc_i_b_done(sstat[9]),.s_adc_q_done(sstat[10]),.s_adc_q_b_done(sstat[11]),
  .s_detect_diff_pos(sstat[12]),.s_detect_diff_neg(sstat[13]),.s_detect_se_p(sstat[14]),.s_detect_se_n(sstat[15]),
  .s_wrx_slp(sstat[16]),.s_wrx_slm(sstat[17]),.s_wtx_ext_data(sstat[18]),.s_aux_present(sstat[19]),.s_wtx_ext_present(sstat[20]),
  `PT_GL_IN_TIE, `PT_GL_OUT_CONN);
 always #10 fclk=~fclk;  // 50 MHz shared fast clock, gated by run_clk (directed section only)

 integer fd,log,code,op,a,b,c,i,ncmd;
 reg[15:0]rd;reg[31:0]frame;
 task spi(input[7:0]cmd,input[7:0]addr,input[15:0]data,output[15:0]q);
  begin
   frame={cmd,addr,data};q=0;cs_n=0;#50;
   for(i=31;i>=0;i=i-1)begin
    mosi=frame[i];#50;sclk=1;if(i<16)q[i]=o_spi_miso;#50;sclk=0;
   end
   #50;cs_n=1;mosi=0;#100;
  end
 endtask
 // Snapshot: one "name=hex" token per macro output, in port order.
 task snap(input[8*4-1:0]tag);
  begin $fwrite(log,"S %0s",tag);gl_dump(log);$fwrite(log,"\n");end
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
     8:begin sstat={b[8:0],a[11:0]};#20;end                       // analog status inputs
     9:begin run_clk=a[0];#(1000*b+20);end                         // gate fast clocks, run b us
     default:begin $display("FATAL bad op %0d",op);$finish;end
    endcase
   end
  end
  $fdisplay(log,"E %0d",ncmd);$fclose(log);$display("tb_digital_gl done: %0d commands",ncmd);$finish;
 end
endmodule
