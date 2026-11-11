// Formal harness for the AC-1 H2D pad-edge capture (rtl/pt_host_link.sv pt_h2d_gearbox), transport
// rework 2026-11-10. multiclock: free pin clock and free pin data (any word on any edge), DDR mode.
// The properties are asserted inside pt_h2d_gearbox (`ifdef FORMAL): every assembled quad is the
// four chronological pin words, and the falling-edge hold register fh is unchanged for the
// 1.5 periods before it is assembled (SDC multicycle 2 host.h2d.fh -> host.h2d.asm).
module pt_h2d_gearbox_fv(input wire clk,rst_n,input wire[9:0]pin,input wire core_clk);
 wire[39:0]quad;wire ov,un;
 pt_h2d_gearbox h2d(.rst_n(rst_n),.mode(2'd0),.h2d_clk(clk),.h2d_pin(pin),.core_clk(core_clk),.core_rst_n(rst_n),
  .quad(quad),.overflow(ov),.underflow(un));
 reg init=1;
 always @($global_clock)begin
  init<=0;
  if(init)assume(!rst_n);
  if(!init&&!$stable(rst_n))assume($stable(clk)&&rst_n);
  if(!init)cover(rst_n&&quad!=0);
 end
endmodule
