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
 pt_provider_input spi_clock(.pad(SPI_SCLK),.y(sclk),.vdd(VDD_HOST_A),.vss(VSS_HOST_A));
 pt_provider_input spi_select(.pad(SPI_CS_N),.y(cs_n),.vdd(VDD_HOST_A),.vss(VSS_HOST_A));
 pt_provider_input spi_data(.pad(SPI_MOSI),.y(mosi),.vdd(VDD_HOST_A),.vss(VSS_HOST_A));
 // retained.py selects bi_t PDRV0=0/PDRV1=1/SL=0 for HOST_MISO.
 pt_provider_output spi_return(.pad(SPI_MISO),.a(miso),.oe(miso_oe),.drive(2'b10),.slew(1'b0),
  .vdd(VDD_HOST_B),.vss(VSS_HOST_B));
 pt_provider_input host_clock(.pad(H2D_CLK),.y(h2d_clk),.vdd(VDD_HOST_A),.vss(VSS_HOST_A));
 for(genvar k=0;k<10;k=k+1) begin: data
  pt_provider_input host_in(.pad(H2D[k]),.y(h2d_pin[k]),.vdd(VDD_HOST_A),.vss(VSS_HOST_A));
  pt_provider_output host_out(.pad(D2H[k]),.a(d2h_pin[k]),.oe(d2h_oe),.drive(d2h_pdrv),.slew(d2h_sl),
   .vdd(VDD_HOST_B),.vss(VSS_HOST_B));
 end
 pt_provider_output host_clock_out(.pad(D2H_CLK),.a(d2h_clk_pin),.oe(d2h_oe),.drive(d2h_pdrv),.slew(d2h_sl),
  .vdd(VDD_HOST_B),.vss(VSS_HOST_B));
endmodule

module pt_debug_physical(
 inout wire VDD_CORE,VSS_CORE,output wire CLK_OBS,DBG_OBS0,DBG_OBS1,WCLK_OBS,WDBG_OBS,
 input wire clk_obs,clk_obs_oe,dbg_obs0,dbg_obs0_oe,dbg_obs1,dbg_obs1_oe,
 input wire wclk_obs,wclk_obs_oe,wdbg_obs,wdbg_obs_oe
);
 wire[4:0] a={wdbg_obs,wclk_obs,dbg_obs1,dbg_obs0,clk_obs};
 wire[4:0] oe={wdbg_obs_oe,wclk_obs_oe,dbg_obs1_oe,dbg_obs0_oe,clk_obs_oe};
 wire[4:0] pad;
 assign {WDBG_OBS,WCLK_OBS,DBG_OBS1,DBG_OBS0,CLK_OBS}=pad;
 for(genvar k=0;k<5;k=k+1) begin: observe
  gf180mcu_fd_io__bi_24t cell_io(.PAD(pad[k]),.A(a[k]),.OE(oe[k]),.Y(),
   .CS(1'b0),.SL(1'b0),.IE(1'b0),.PU(1'b0),.PD(1'b0),
   .DVDD(VDD_CORE),.DVSS(VSS_CORE),.VDD(VDD_CORE),.VSS(VSS_CORE));
 end
endmodule

module pt_provider_input(inout wire pad,output wire y,inout wire vdd,vss);
 gf180mcu_fd_io__bi_24t cell_io(.PAD(pad),.Y(y),.A(1'b0),.OE(1'b0),
  .CS(1'b0),.SL(1'b0),.IE(1'b1),.PU(1'b0),.PD(1'b0),
  .DVDD(vdd),.DVSS(vss),.VDD(vdd),.VSS(vss));
endmodule

module pt_provider_output(output wire pad,input wire a,oe,input wire[1:0]drive,
 input wire slew,inout wire vdd,vss);
 gf180mcu_fd_io__bi_t cell_io(.PAD(pad),.A(a),.OE(oe),.Y(),
  .PDRV0(drive[0]),.PDRV1(drive[1]),.CS(1'b0),.SL(slew),.IE(1'b0),.PU(1'b0),.PD(1'b0),
  .DVDD(vdd),.DVSS(vss),.VDD(vdd),.VSS(vss));
endmodule
`default_nettype wire
