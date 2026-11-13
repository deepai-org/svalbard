`timescale 1ns/1ps
// Digital integration check through pt_chip and the unmodified provider pads.
// Explicit analog-boundary stimuli below are NOT power-up/island qualification.
// No control, SPI, register-file or pad outputs are forced.
module tb_chip_io;
 initial begin $dumpfile("chip-io.vcd"); $dumpvars(1,dut); end
 reg reset_drive=0, sclk_drive=0, cs_drive=1, mosi_drive=0;
 wire RESET_N=reset_drive;
 wire SPI_SCLK=sclk_drive, SPI_CS_N=cs_drive, SPI_MOSI=mosi_drive;
 wire SPI_MISO; wire[9:0] D2H; wire D2H_CLK;
 wire DBG_OBS0,DBG_OBS1,CLK_OBS,WCLK_OBS,WDBG_OBS;
 supply1 vdd; supply0 vss; wire[9:0] h2d=0; wire h2d_clk=0;
 reg por=0; reg[5:0] pg=0;
 pt_chip dut(.RESET_N(RESET_N),.SPI_SCLK(SPI_SCLK),.SPI_CS_N(SPI_CS_N),.SPI_MOSI(SPI_MOSI),
  .SPI_MISO(SPI_MISO),.H2D(h2d),.H2D_CLK(h2d_clk),.D2H(D2H),.D2H_CLK(D2H_CLK),
  .REF_IN(1'b0),.REF_IN_N(1'b0),.AUX_CLK_P(1'b0),.AUX_CLK_N(1'b0),
  .WCLK_IN_P(1'b0),.WCLK_IN_N(1'b0),.WTX_EXT_P(1'b0),.WTX_EXT_N(1'b0),
  .DBG_OBS0(DBG_OBS0),.DBG_OBS1(DBG_OBS1),.CLK_OBS(CLK_OBS),.WCLK_OBS(WCLK_OBS),.WDBG_OBS(WDBG_OBS),
  .VDD_CORE(vdd),.VSS_CORE(vss),.VDD_HOST_A(vdd),.VSS_HOST_A(vss),.VDD_HOST_B(vdd),.VSS_HOST_B(vss),
  .VDD_WIRE_A(vdd),.VSS_WIRE_A(vss),.VDD_WIRE_B(vdd),.VSS_WIRE_B(vss),
  .VDD_RF(vdd),.VSS_RF(vss),.VDD_PLL(vdd),.VSS_PLL(vss));
 initial begin
  force dut.por_n=por;
  force dut.island_pgood=pg;
  force dut.fault=1'b0;
  force dut.analog_status=12'b0;
  force dut.wire_analog_status=13'b0;
 end
 task spi(input[7:0] command,address,input[15:0] value,output[15:0] result);
  reg[31:0] tx; integer i;
  begin
   tx={command,address,value}; result=0;
   cs_drive=0; #100;
   for(i=31;i>=0;i=i-1) begin
    mosi_drive=tx[i]; #200; sclk_drive=1; #200;
    if(i<16) result[i]=SPI_MISO;
    sclk_drive=0; #100;
   end
   cs_drive=1; #100;
   if(SPI_MISO!==1'bz) $fatal(1,"MISO did not release after CS_N");
  end
 endtask
 reg[15:0] result;
 task write_reg(input[7:0] address,input[15:0] value);
  begin spi(8'h80,address,value,result); end
 endtask
 task read_reg(input[7:0] address,input[15:0] expected);
  begin
   spi(0,address,0,result);
   if(result!==expected) $fatal(1,"read %h: got %h expected %h",address,result,expected);
  end
 endtask
 task released;
  begin
   #20;
   if({D2H_CLK,D2H}!==11'bz || {WDBG_OBS,WCLK_OBS,DBG_OBS1,DBG_OBS0,CLK_OBS}!==5'bz)
    $fatal(1,"host/debug pads driven during reset/defaults");
   if(dut.island_en!==0 || dut.atb0_sw!==0 || dut.atb1_sw!==0)
    $fatal(1,"island or ATB not reset off");
  end
 endtask
 initial begin
  #50; released();
  // CS low during reset must not turn on the MISO driver.
  cs_drive=0; #100;
  if(SPI_MISO!==1'bz) $fatal(1,"MISO drives while reset is asserted");
  cs_drive=1; por=1; reset_drive=1; #100;
  read_reg(0,16'h5356); read_reg(8'h0d,16'h0003); read_reg(8'h0a,0);
  write_reg(8'h40,1); write_reg(6,1);
  if(dut.island_en!==6'b000001 || dut.island_on!==0) $fatal(1,"island must wait for power-good");
  write_reg(8'h4e,4); write_reg(6,1); #50;
  if(DBG_OBS0!==0) $fatal(1,"wired PG observation low");
  // Boundary stimulus stands in for the missing physical island in THIS test.
  pg=1; #50;
  read_reg(8'h0a,16'h0101);
  if(DBG_OBS0!==1) $fatal(1,"wired PG did not reach the debug pad");
  pg=0; #50;
  read_reg(8'h0a,0);
  if(DBG_OBS0!==0 || dut.island_on!==0) $fatal(1,"PG loss not observed/isolated");
  // Assert reset in an active SPI transaction, without further SCLK edges.
  cs_drive=0; #100; reset_drive=0; #100;
  if(SPI_MISO!==1'bz) $fatal(1,"MISO reset release needs clocks");
  released(); cs_drive=1; reset_drive=1; #100;
  read_reg(0,16'h5356); read_reg(8'h40,0);
  // The provider's in_c Verilog ignores PU/PD; check the binding here.
  // Floating-pin voltage must be checked with its transistor netlist.
  if(dut.host.reset_pad.PD!==1 || dut.host.reset_pad.PU!==0)
   $fatal(1,"RESET_N pull-down binding");
  // POR must also gate MISO even with the board reset released.
  cs_drive=0; #100; por=0; #100;
  if(SPI_MISO!==1'bz) $fatal(1,"POR did not release MISO");
  released();
  $display("CHIP_IO_PASS"); $finish;
 end
 initial begin #1000000; $fatal(1,"chip IO timeout"); end
endmodule
