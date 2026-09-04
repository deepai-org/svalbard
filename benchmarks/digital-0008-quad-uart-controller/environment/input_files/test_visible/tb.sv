`timescale 1ns/1ps
module tb;
  logic clk=0, rst_n=0; always #5 clk=~clk;
  logic [3:0] en=4'hf, txv=0, txr, rxv, rxready=0, urx=4'hf, utx;
  logic [63:0] divs={16'd11,16'd9,16'd7,16'd5};
  logic [31:0] txd=0, rxd; logic [3:0] clr=0, frame, over;
  quad_uart_controller dut(
    .clk_i(clk), .rst_ni(rst_n), .enable_i(en), .baud_div_i(divs),
    .tx_data_i(txd), .tx_valid_i(txv), .tx_ready_o(txr),
    .rx_data_o(rxd), .rx_valid_o(rxv), .rx_ready_i(rxready),
    .uart_rx_i(urx), .uart_tx_o(utx), .error_clear_i(clr),
    .framing_error_o(frame), .overrun_error_o(over)
  );
  task send_tx(input integer c, input [7:0] b);
    begin
      @(negedge clk); txd[c*8 +: 8]=b; txv[c]=1;
      while (!txr[c]) @(negedge clk);
      @(negedge clk); txv[c]=0;
    end
  endtask
  task expect_serial(input integer c, input [7:0] b, input integer d);
    integer k;
    begin
      wait(utx[c]===0); repeat(d/2) @(posedge clk);
      if (utx[c]!==0) $fatal(1,"start");
      for(k=0;k<8;k=k+1) begin repeat(d) @(posedge clk); if(utx[c]!==b[k]) $fatal(1,"data"); end
      repeat(d) @(posedge clk); if(utx[c]!==1) $fatal(1,"stop");
    end
  endtask
  initial begin
    repeat(3) @(posedge clk); rst_n=1; fork send_tx(0,8'ha5); expect_serial(0,8'ha5,5); join
    if (utx!==4'hf || frame || over) $fatal(1,"idle/status");
    $display("VISIBLE_PASS"); $finish;
  end
  initial begin #20000; $fatal(1,"timeout"); end
endmodule
