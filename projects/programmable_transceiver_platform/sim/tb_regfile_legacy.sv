// Lockstep equivalence of the legacy pt_control boundary: sim/reference/pt_control.sv
// and the generated pt_mgmt share every SPI pin and legacy input. Random transactions
// target the legacy addresses and addresses that are unassigned in both maps. MISO
// (sampled at every rising SCLK edge) and every legacy output must match.
// Address 0x08 (ABI version) is excluded: it deliberately changed from 0x0001 to 0x0003.
// MEMORY v3 (ABI 0x0003, AC-1 sharing S1) deliberately changed the MEMORY data path: quads are
// 40-bit (0x21/0x24 staging, 0x24-0x26 capture readback), 0x23 gained loop/last. Their read data
// (0x21-0x26) and the memory write data are excluded; the write event and its INDEX, the enables and
// the ENABLE=1 rejection of 0x21-0x23 still match. 0x24 is only read (a v3 staging write would be a
// new rejection while ENABLE=1).
`timescale 1ns/1ps
`include "pt_regmap_defs.svh"
module tb_regfile_legacy;
 reg rst_n=1,sclk=0,cs_n=0,mosi=0;reg[15:0]status=0;reg[23:0]capture_data=0;reg capture_done=0;
 wire miso_a,oe_a,en_a,m8_a,mw_a,pb_a,ce_a;wire[15:0]rt_a,wt_a,ct_a;wire[4:0]mi_a;wire[23:0]md_a;
 wire miso_b,oe_b,en_b,m8_b,mw_b,pb_b,ce_b;wire[15:0]rt_b,wt_b,ct_b;wire[4:0]mi_b;wire[39:0]md_b;
 pt_control old(rst_n,sclk,cs_n,mosi,miso_a,oe_a,status,en_a,m8_a,rt_a,wt_a,ct_a,mw_a,mi_a,md_a,capture_data,capture_done,pb_a,ce_a);
 pt_mgmt neu(.rst_n(rst_n),.por_n(rst_n),.por_bypass(1'b0),.sclk(sclk),.cs_n(cs_n),.mosi(mosi),.miso(miso_b),.miso_oe(oe_b),.status(status),
  .enable(en_b),.mode8(m8_b),.rf_trim(rt_b),.wire_trim(wt_b),.clock_trim(ct_b),.memory_write(mw_b),
  .memory_index(mi_b),.memory_wdata(md_b),.capture_data({16'd0,capture_data}),.memory_loop(),.memory_last(),.capture_done(capture_done),
  .playback_enable(pb_b),.capture_enable(ce_b),.fault(1'b0),.island_pgood({`PT_ISLAND_W{1'b0}}),.obs_status(32'h0),
  .wire_status(16'h0),.analog_cfg(),.debug_cfg(),.island_en(),.island_on(),.atb0_sw(),.atb1_sw(),.rx_en_aux(),
  .rx_en_wclk(),.rx_en_wtx_ext(),.clk_obs_oe(),.wclk_obs_oe(),.dbg_obs0(),.dbg_obs0_oe(),.dbg_obs1(),.dbg_obs1_oe(),
  .wdbg_obs(),.wdbg_obs_oe(),.commit_toggle(),.config_error(),
  .pattern_locked(1'b0),.pattern_lost_lock(1'b0),.pattern_errors_gray(16'h0),.fca_locked(1'b0),.fca_lost(1'b0),.fca_diff(14'd0),.fca_count(16'd0),.fcb_locked(1'b0),.fcb_lost(1'b0),.fcb_diff(14'd0),.fcb_count(16'd0));
 integer i,n,errors=0,writes=0,reads=0,mw_seen=0,seed=7;reg[7:0]addr,cmd;reg[15:0]data;reg[31:0]frame;reg check_miso;
 reg[7:0]addrs[0:22];
 // Register outputs are compared at every rising SCLK edge. The memory write is compared as an event:
 // the reference completes a write on the 32nd rising edge, pt_mgmt on the falling edge after it
 // (rtl/pt_spi.sv), so each side's (index, data) at its own write edge is recorded per transaction.
 wire legacy_match=oe_a===oe_b&&en_a===en_b&&m8_a===m8_b&&rt_a===rt_b&&wt_a===wt_b&&ct_a===ct_b&&
  mi_a===mi_b&&pb_a===pb_b&&ce_a===ce_b;
 reg[29:0]ev_a,ev_b;integer nev_a=0,nev_b=0;
 always @(posedge sclk)begin
  if(check_miso&&!(addr>=8'h21&&addr<=8'h26)&&miso_a!==miso_b)begin errors=errors+1;if(errors<10)$display("MISO mismatch addr %h",addr);end
  if(!legacy_match)begin errors=errors+1;if(errors<10)$display("output mismatch addr %h",addr);end
  if(mw_a)begin mw_seen=mw_seen+1;ev_a={1'b1,mi_a,24'd0};nev_a=nev_a+1;end
 end
 always @(negedge sclk)if(mw_b)begin ev_b={1'b1,mi_b,24'd0};nev_b=nev_b+1;end
 task check_events;begin
  if(nev_a!==nev_b||ev_a!==ev_b)begin errors=errors+1;if(errors<10)$display("memory write mismatch addr %h",addr);end
  nev_a=0;nev_b=0;ev_a=0;ev_b=0;
 end endtask
 initial begin
  addrs[0]=8'h00;addrs[1]=8'h01;addrs[2]=8'h02;addrs[3]=8'h03;addrs[4]=8'h04;addrs[5]=8'h10;addrs[6]=8'h11;
  addrs[7]=8'h12;addrs[8]=8'h20;addrs[9]=8'h21;addrs[10]=8'h22;addrs[11]=8'h23;addrs[12]=8'h24;addrs[13]=8'h25;
  addrs[14]=8'h26;addrs[15]=8'h30;addrs[16]=8'h3F;addrs[17]=8'hF0;addrs[18]=8'hFF;addrs[19]=8'h01;addrs[20]=8'h04;
  addrs[21]=8'h23;addrs[22]=8'h22;
  check_miso=0;#5;cs_n=1;#5;rst_n=0;#50;rst_n=1;#50;
  for(n=0;n<4000;n=n+1)begin
   addr=addrs[$unsigned($random(seed))%23];
   cmd=($random(seed)&1)?8'h80:8'h00;if(addr==8'h24)cmd=8'h00;
   data=$random(seed);if(addr==8'h01&&($random(seed)&3)!=0)data=0;
   status=$random(seed);capture_data=$random(seed);capture_done=$random(seed);
   if(cmd==8'h80)writes=writes+1;else reads=reads+1;
   frame={cmd,addr,data};cs_n=0;check_miso=1;#50;
   for(i=31;i>=0;i=i-1)begin mosi=frame[i];#50;sclk=1;#50;sclk=0;end
   #50;cs_n=1;check_miso=0;#100;check_events;
   if(($random(seed)%97)==0)begin rst_n=0;#30;rst_n=1;#50;end
  end
  if(!legacy_match)errors=errors+1;
  $display("legacy equivalence: %0d transactions (%0d writes, %0d reads, %0d memory writes), %0d mismatches",
   n,writes,reads,mw_seen,errors);
  if(errors==0)$display("PASS");else $display("FAIL");
  $finish;
 end
endmodule
