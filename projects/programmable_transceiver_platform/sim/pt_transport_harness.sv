`timescale 1ns/1ps
// Test harness for the AC-1 transport: the real pad-edge host link
// (pt_host_link: hcore divider, H2D DDR capture + 1:4 gearbox + quad FIFO,
// D2H XOR-prefix 4:1 gearbox + DDR launch) in front of the real 40-bit core
// (pt_core). The FPGA side is modelled at the ten-bit word level on the host
// word clock hclk, through ideal pins:
//   H2D: the FPGA word stream changes on each hclk rising edge; the forwarded
//        H2D clock is hclk/2 toggling on the hclk falling edge (centre aligned,
//        DDR: one word per H2D clock edge, any word/quad phase).
//   D2H: the pins are sampled on the hclk falling edge (mid-word) and handed
//        to the FPGA receiver on the next hclk rising edge.
// HOST_MODE 1 exercises the SDR capture path (forwarded H2D clock = hclk).
module pt_transport_harness #(parameter HOST_MODE=0,LINECODE=0)(input wire rst_n,enable,mode8,
 input wire hclk,wire_rx_clk,wire_tx_clk,rf_rx_clk,rf_tx_clk,
 input wire[9:0]h2d_word,output reg[9:0]d2h_word,
 input wire[39:0]wire_rx_data,input wire wire_rx_valid,
 output wire[39:0]wire_tx_data,output wire wire_tx_valid,input wire wire_tx_request,
 input wire[23:0]rf_rx_sample,input wire rf_rx_valid,
 output wire[23:0]rf_tx_sample,output wire rf_tx_valid,input wire rf_tx_request,
 output wire[15:0]status,output wire wire_idle,rf_mute,input wire payload_iq,
 output wire[6:0]rx_gain,output wire rx_gain_active);
 reg h2d_clk=0;
 always @(negedge hclk)h2d_clk<=HOST_MODE?1'b0:!h2d_clk;
 wire h2d_pin_clk=HOST_MODE?!hclk:h2d_clk;
 wire core_clk,core_rst_n;wire[39:0]h2d_quad,d2h_quad;wire[9:0]d2h_pin;
 reg hddr=0;always @(posedge hclk)hddr<=!hddr;   // host DDR clock = word clock / 2
 wire d2h_clk_pin,d2h_oe,h2d_overflow,h2d_underflow;
 pt_host_link host(.rst_n(rst_n),.mode(2'(HOST_MODE)),.d2h_enable(1'b1),.h2d_clk(h2d_pin_clk),.h2d_pin(h2d_word),
  .link_clk(hddr),.word_clk(hclk),.core_clk(core_clk),.core_rst_n(core_rst_n),.h2d_quad(h2d_quad),.d2h_quad(d2h_quad),.d2h_pin(d2h_pin),
  .d2h_clk_pin(d2h_clk_pin),.d2h_stagger(1'b0),.d2h_oe(d2h_oe),.h2d_overflow(h2d_overflow),.h2d_underflow(h2d_underflow));
 always @(negedge hclk)d2h_word<=d2h_pin;
 pt_core core(.rst_n(core_rst_n),.enable(enable),.mode8(mode8),.host_clk(core_clk),
  .wire_rx_clk(wire_rx_clk),.wire_tx_clk(wire_tx_clk),.rf_rx_clk(rf_rx_clk),.rf_tx_clk(rf_tx_clk),
  .h2d_quad(h2d_quad),.d2h_quad(d2h_quad),.wire_rx_data(wire_rx_data),.wire_rx_valid(wire_rx_valid),
  .wire_tx_data(wire_tx_data),.wire_tx_valid(wire_tx_valid),.wire_tx_request(wire_tx_request),
  .rf_rx_sample(rf_rx_sample),.rf_rx_valid(rf_rx_valid),.rf_tx_sample(rf_tx_sample),.rf_tx_valid(rf_tx_valid),
  .rf_tx_request(rf_tx_request),.status(status),.wire_idle(wire_idle),.rf_mute(rf_mute),.payload_iq(payload_iq),
  .linecode(1'(LINECODE)),.rx_gain(rx_gain),.rx_gain_active(rx_gain_active),
  .mem_capture(1'b0),.mem_play(1'b0),.mem_loop(1'b0),.mem_last(5'd0),.spi_clk(1'b0),.mem_we(1'b0),.mem_idx(5'd0),
  .mem_wdata(40'd0),.mem_rdata(),.capture_done());
 // The host FIFO must never over/underflow once the link runs (mesochronous).
 always @(posedge core_clk)if(rst_n&&(h2d_overflow||h2d_underflow))
  $fatal(1,"H2D quad FIFO %s",h2d_overflow?"overflow":"underflow");
endmodule
