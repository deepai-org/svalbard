// Command-driven SPI testbench for pt_mgmt (pt_spi + generated pt_regfile).
// verification/check_regfile.py writes the command file, runs this bench under
// iverilog and verilator, and compares the log against the generated reference
// model (rtl/gen/pt_regmap.py). The bench itself only drives pins and logs.
`timescale 1ns/1ps
`include "pt_regmap_defs.svh"
module tb_regfile;
 reg rst_n=1,por_n=1,sclk=0,cs_n=0,mosi=0,fault=0;
 reg[5:0]pgood=0;reg pat_locked=0,pat_lost=0;reg[15:0]pat_err_gray=0;
 wire miso,miso_oe,enable,mode8,memory_write,playback_enable,capture_enable,commit_toggle,config_error;
 wire[15:0]rf_trim,wire_trim,clock_trim;wire[4:0]memory_index;wire[23:0]memory_wdata;
 wire[`PT_ANALOG_CFG_W-1:0]analog_cfg;wire[`PT_DEBUG_CFG_W-1:0]debug_cfg;
 wire[`PT_ISLAND_W-1:0]island_en,island_on;wire[`PT_ATB_W-1:0]atb0_sw,atb1_sw;
 wire rx_en_aux,rx_en_wclk,rx_en_wtx_ext,clk_obs_oe,wclk_obs_oe,atb0_en,atb1_en;
 wire[`PT_ATB0_GRP_W-1:0]atb0_grp;wire[`PT_ATB1_GRP_W-1:0]atb1_grp;
 wire dbg_obs0,dbg_obs0_oe,dbg_obs1,dbg_obs1_oe,wdbg_obs,wdbg_obs_oe;
 localparam[15:0]STATUS=16'hA5C3;localparam[31:0]OBS=32'h9E37_79B9;localparam[15:0]WSTAT=16'h6A09;
 localparam[23:0]CAPTURE=24'h5A_1234;
 pt_mgmt dut(.rst_n(rst_n),.por_n(por_n),.sclk(sclk),.cs_n(cs_n),.mosi(mosi),.miso(miso),.miso_oe(miso_oe),
  .status(STATUS),.enable(enable),.mode8(mode8),.rf_trim(rf_trim),.wire_trim(wire_trim),.clock_trim(clock_trim),
  .memory_write(memory_write),.memory_index(memory_index),.memory_wdata(memory_wdata),
  .capture_data(CAPTURE),.capture_done(1'b0),.playback_enable(playback_enable),.capture_enable(capture_enable),
  .fault(fault),.island_pgood(pgood),.obs_status(OBS),.wire_status(WSTAT),
  .analog_cfg(analog_cfg),.debug_cfg(debug_cfg),.island_en(island_en),.island_on(island_on),
  .atb0_sw(atb0_sw),.atb1_sw(atb1_sw),.atb0_grp(atb0_grp),.atb1_grp(atb1_grp),.atb0_en(atb0_en),.atb1_en(atb1_en),.rx_en_aux(rx_en_aux),.rx_en_wclk(rx_en_wclk),.rx_en_wtx_ext(rx_en_wtx_ext),
  .clk_obs_oe(clk_obs_oe),.wclk_obs_oe(wclk_obs_oe),.dbg_obs0(dbg_obs0),.dbg_obs0_oe(dbg_obs0_oe),
  .dbg_obs1(dbg_obs1),.dbg_obs1_oe(dbg_obs1_oe),.wdbg_obs(wdbg_obs),.wdbg_obs_oe(wdbg_obs_oe),
  .commit_toggle(commit_toggle),.config_error(config_error),
  .pattern_locked(pat_locked),.pattern_lost_lock(pat_lost),.pattern_errors_gray(pat_err_gray),
  .fca_locked(1'b0),.fca_lost(1'b0),.fca_diff(14'd0),.fca_count(16'd0),.fcb_locked(1'b0),.fcb_lost(1'b0),.fcb_diff(14'd0),.fcb_count(16'd0));

 integer fd,log,code,op,a,b,c,i,ncmd;
 reg[15:0]rd;reg[31:0]frame;
 // 10 MHz SCLK, mode 0: MOSI changes on falling edge, sampled on rising edge.
 task spi(input[7:0]cmd,input[7:0]addr,input[15:0]data,output[15:0]q);
  begin
   frame={cmd,addr,data};q=0;cs_n=0;#50;
   for(i=31;i>=0;i=i-1)begin
    mosi=frame[i];#50;sclk=1;if(i<16)q[i]=miso;#50;sclk=0;
   end
   #50;cs_n=1;mosi=0;#100;
  end
 endtask
 task snap(input[8*4-1:0]tag);
  $fdisplay(log,"S %0s %h %h %h %h %h %h %b%b%b%b%b %b%b%b%b%b%b %b%b %h %h %h %h %h %h %h %b%b",tag,analog_cfg,debug_cfg,island_en,island_on,
   atb0_sw,atb1_sw,rx_en_aux,rx_en_wclk,rx_en_wtx_ext,clk_obs_oe,wclk_obs_oe,
   dbg_obs0,dbg_obs0_oe,dbg_obs1,dbg_obs1_oe,wdbg_obs,wdbg_obs_oe,commit_toggle,config_error,
   {7'b0,enable},{7'b0,mode8},{6'b0,playback_enable,capture_enable},miso_oe,miso,atb0_grp,atb1_grp,atb0_en,atb1_en);
 endtask
 initial begin
  fd=$fopen("commands.txt","r");log=$fopen("tb.log","w");
  if(fd==0)begin $display("FATAL no commands.txt");$finish;end
  // Create the edges the event-driven model of pt_spi needs (its serial reset is rst_n&&!cs_n;
  // silicon async reset is level-sensitive, an event simulator only reacts to edges).
  #5;cs_n=1;#5;rst_n=0;por_n=0;#90;snap("R0");por_n=1;rst_n=1;#100;ncmd=0;
  while(!$feof(fd))begin
   code=$fscanf(fd,"%d %h %h %h\n",op,a,b,c);
   if(code==4)begin
    ncmd=ncmd+1;
    case(op)
     0:spi(8'h80,a[7:0],b[15:0],rd);
     1:begin spi(8'h00,a[7:0],16'h0,rd);$fdisplay(log,"R %h %h",a[7:0],rd);end
     2:begin pgood=a[5:0];fault=b[0];#20;end
     3:begin rst_n=0;#30;snap("RST");#30;rst_n=1;#100;end
     4:snap("SNAP");
     5:begin // reset asserted in the middle of a write transaction
       frame={8'h80,a[7:0],b[15:0]};cs_n=0;#50;
       for(i=31;i>=16;i=i-1)begin mosi=frame[i];#50;sclk=1;#50;sclk=0;end
       #20;rst_n=0;#30;snap("MID");#30;cs_n=1;mosi=0;#50;rst_n=1;#100;
      end
     6:begin rst_n=0;por_n=0;#30;snap("POR");#30;por_n=1;rst_n=1;#100;end // power-on reset
     7:begin pat_locked=a[0];pat_lost=a[1];pat_err_gray=b[15:0];#20;end // read-only status sources
     default:begin $display("FATAL bad op %0d",op);$finish;end
    endcase
   end
  end
  $fdisplay(log,"E %0d",ncmd);$fclose(log);$display("tb_regfile done: %0d commands",ncmd);$finish;
 end
endmodule
