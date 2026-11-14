// Concrete retained I/O binding for pt_chip. Compile with PT_EXTERNAL_IO.
// Cell ports match the pinned gf180mcuD provider Verilog and SPICE library.
// Logical supply groups connect to the provider's one common external rail;
// this hierarchy does not implement the physical supply ring or its bonds.
`default_nettype none
module pt_host_physical(
 inout wire RESET_N,SPI_SCLK,SPI_CS_N,SPI_MOSI,output wire SPI_MISO,
 inout wire[9:0]H2D,inout wire H2D_CLK,output wire[9:0]D2H,output wire D2H_CLK,
 inout wire VDD_CORE,VSS_CORE,VDD_HOST_A,VSS_HOST_A,VDD_HOST_B,VSS_HOST_B,
 output wire rst_n,sclk,cs_n,mosi,input wire miso,miso_oe,
 output wire h2d_clk,output wire[9:0]h2d_pin,input wire[9:0]d2h_pin,
 input wire d2h_clk_pin,d2h_oe,input wire[1:0]d2h_pdrv,input wire d2h_sl
);
 gf180mcu_fd_io__in_c reset_pad(.PAD(RESET_N),.Y(rst_n),.PU(1'b0),.PD(1'b1),
  .DVDD(VDD_CORE),.DVSS(VSS_CORE),.VDD(VDD_CORE),.VSS(VSS_CORE));
 // SPI inputs (DT-11, 2026-11-13): Schmitt input on the two edge-sensitive pins (SCLK clocks, CS_N
 // asynchronously resets the bit counter), and pad pulls to the idle level so that a hi-Z or absent
 // host leaves a defined Mode-0 idle state: CS_N high (deselected), SCLK low, MOSI low. That idle
 // state is also the "no override" state of the pad-free POR path (rtl/pt_por_path.sv).
 // bi_24t provides CS / PU / PD pins (provider Verilog + Liberty: PAD->Y arcs for CS = 0 and CS = 1);
 // the pulls act only with OE = 0, which is hard-tied here. Hard ties, never register-driven.
 // Each pad Y drives ONE repeater (clkbuf_8 class) within ~200 um, Y load < 0.1 pF (DT-11).
 pt_provider_input #(.SCHMITT(1),.PULL_DOWN(1)) spi_clock(.pad(SPI_SCLK),.y(sclk),.vdd(VDD_HOST_A),.vss(VSS_HOST_A));
 pt_provider_input #(.SCHMITT(1),.PULL_UP(1)) spi_select(.pad(SPI_CS_N),.y(cs_n),.vdd(VDD_HOST_A),.vss(VSS_HOST_A));
 pt_provider_input #(.SCHMITT(1),.PULL_DOWN(1)) spi_data(.pad(SPI_MOSI),.y(mosi),.vdd(VDD_HOST_A),.vss(VSS_HOST_A)); // Schmitt: MOSI is in the asynchronous dead-man clear of rtl/pt_por_path.sv (review P4/S5)
 // retained.py selects bi_t PDRV0=0/PDRV1=1/SL=0 for HOST_MISO.
 pt_provider_output spi_return(.pad(SPI_MISO),.a(miso),.oe(miso_oe),.drive(2'b10),.slew(1'b0),
  .vdd(VDD_HOST_B),.vss(VSS_HOST_B));
 // INT6-5 / TOP-25 (6): pad pull-downs on the host inputs, so an unconfigured or absent FPGA leaves no floating
 // CMOS input (CMOS thresholds kept: CS = 1 costs speed at 156.25 MHz). Weak provider pull, hard tie.
 pt_provider_input #(.PULL_DOWN(1)) host_clock(.pad(H2D_CLK),.y(h2d_clk),.vdd(VDD_HOST_A),.vss(VSS_HOST_A));
 for(genvar k=0;k<10;k=k+1) begin: data
  pt_provider_input #(.PULL_DOWN(1)) host_in(.pad(H2D[k]),.y(h2d_pin[k]),.vdd(VDD_HOST_A),.vss(VSS_HOST_A));
  pt_provider_output host_out(.pad(D2H[k]),.a(d2h_pin[k]),.oe(d2h_oe),.drive(d2h_pdrv),.slew(d2h_sl),
   .vdd(VDD_HOST_B),.vss(VSS_HOST_B));
 end
 pt_provider_output host_clock_out(.pad(D2H_CLK),.a(d2h_clk_pin),.oe(d2h_oe),.drive(d2h_pdrv),.slew(d2h_sl),
  .vdd(VDD_HOST_B),.vss(VSS_HOST_B));
endmodule

// Observation pads. PD22: WCLK_OBS / WDBG_OBS are retired (their sites are USB_DP / USB_DN); the wired status and
// clocks are observed on DBG_OBS0/1 and CLK_OBS.
module pt_debug_physical(
 inout wire VDD_CORE,VSS_CORE,output wire CLK_OBS,DBG_OBS0,DBG_OBS1,
 input wire clk_obs,clk_obs_oe,dbg_obs0,dbg_obs0_oe,dbg_obs1,dbg_obs1_oe
);
 wire[2:0] a={dbg_obs1,dbg_obs0,clk_obs};
 wire[2:0] oe={dbg_obs1_oe,dbg_obs0_oe,clk_obs_oe};
 wire[2:0] pad;
 assign {DBG_OBS1,DBG_OBS0,CLK_OBS}=pad;
 for(genvar k=0;k<3;k=k+1) begin: observe
  gf180mcu_fd_io__bi_24t cell_io(.PAD(pad[k]),.A(a[k]),.OE(oe[k]),.Y(),
   .CS(1'b0),.SL(1'b0),.IE(1'b0),.PU(1'b0),.PD(1'b0),
   .DVDD(VDD_CORE),.DVSS(VSS_CORE),.VDD(VDD_CORE),.VSS(VSS_CORE));
 end
endmodule

// POR_BYPASS strap pad (DT-10, D-POR; demand: scratch/digital-timing-close/por-strap-pad-demand.md): INPUT-ONLY
// provider cell in_c with the pull-down hard-tied on (PU = 0, PD = 1: the same proven binding as RESET_N), on the
// always-on core rail. Unbonded or undriven it reads 0 = the POR stays in the reset path. Never bidirectional,
// never register-controlled, nothing else on the pad.
module pad_strap(inout wire PAD,output wire Y,inout wire VDD,VSS);
 gf180mcu_fd_io__in_c strap(.PAD(PAD),.Y(Y),.PU(1'b0),.PD(1'b1),.DVDD(VDD),.DVSS(VSS),.VDD(VDD),.VSS(VSS));
endmodule

// Input-only use of bi_24t (OE = 0, A = 0 hard ties). SCHMITT -> CS (0 CMOS, 1 Schmitt input),
// PULL_UP -> PU, PULL_DOWN -> PD (never both). Defaults = the previous binding (CMOS, no pull).
module pt_provider_input #(parameter SCHMITT=0,PULL_UP=0,PULL_DOWN=0)
 (inout wire pad,output wire y,inout wire vdd,vss);
 if(PULL_UP&&PULL_DOWN) begin: bad_pull initial $fatal(1,"pt_provider_input: PULL_UP and PULL_DOWN both set"); end
 gf180mcu_fd_io__bi_24t cell_io(.PAD(pad),.Y(y),.A(1'b0),.OE(1'b0),
  .CS(SCHMITT?1'b1:1'b0),.SL(1'b0),.IE(1'b1),.PU(PULL_UP?1'b1:1'b0),.PD(PULL_DOWN?1'b1:1'b0),
  .DVDD(vdd),.DVSS(vss),.VDD(vdd),.VSS(vss));
endmodule

module pt_provider_output(output wire pad,input wire a,oe,input wire[1:0]drive,
 input wire slew,inout wire vdd,vss);
 gf180mcu_fd_io__bi_t cell_io(.PAD(pad),.A(a),.OE(oe),.Y(),
  .PDRV0(drive[0]),.PDRV1(drive[1]),.CS(1'b0),.SL(slew),.IE(1'b0),.PU(1'b0),.PD(1'b0),
  .DVDD(vdd),.DVSS(vss),.VDD(vdd),.VSS(vss));
endmodule
`default_nettype wire
