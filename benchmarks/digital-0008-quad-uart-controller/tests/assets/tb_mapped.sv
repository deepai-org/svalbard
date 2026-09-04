`timescale 1ns/1ps
module tb_mapped;
  logic clk=0,rst_n=0; always #5 clk=~clk;
  logic [3:0] en=4'hf,txv=0,txr,rxv,rxready=0,urx=4'hf,utx;
  logic [63:0] divs={4{16'd5}};
  logic [31:0] txd=0,rxd; logic [3:0] clr=0,frame,over;
  quad_uart_controller dut(
    .clk_i(clk), .rst_ni(rst_n), .enable_i(en), .baud_div_i(divs),
    .tx_data_i(txd), .tx_valid_i(txv), .tx_ready_o(txr),
    .rx_data_o(rxd), .rx_valid_o(rxv), .rx_ready_i(rxready),
    .uart_rx_i(urx), .uart_tx_o(utx), .error_clear_i(clr),
    .framing_error_o(frame), .overrun_error_o(over)
  );
  integer k;
  initial begin
    repeat(4)@(posedge clk);rst_n=1;
    @(negedge clk);txd[7:0]=8'ha6;txv[0]=1;
    while(!txr[0])@(negedge clk);@(negedge clk);txv[0]=0;
    wait(utx[0]===0);repeat(2)@(posedge clk);
    for(k=0;k<8;k=k+1)begin repeat(5)@(posedge clk);if(utx[0]!==((8'ha6>>k)&1))$fatal(1,"mapped TX");end
    repeat(5)@(posedge clk);if(utx[0]!==1||frame||over)$fatal(1,"mapped status");
    $display("MAPPED_PASS");$finish;
  end
  initial begin #20000;$fatal(1,"timeout");end
endmodule
