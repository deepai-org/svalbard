`timescale 1ns/1ps
module tb_hidden;
  logic clk=0,rst_n=0; always #5 clk=~clk;
  logic [3:0] en=4'hf,txv=0,txr,rxv,rxready=0,urx=4'hf,utx;
  logic [63:0] divs={16'd11,16'd9,16'd7,16'd5};
  logic [31:0] txd=0,rxd; logic [3:0] clr=0,frame,over;
  quad_uart_controller dut(
    .clk_i(clk), .rst_ni(rst_n), .enable_i(en), .baud_div_i(divs),
    .tx_data_i(txd), .tx_valid_i(txv), .tx_ready_o(txr),
    .rx_data_o(rxd), .rx_valid_o(rxv), .rx_ready_i(rxready),
    .uart_rx_i(urx), .uart_tx_o(utx), .error_clear_i(clr),
    .framing_error_o(frame), .overrun_error_o(over)
  );
  task automatic put(input integer c,input [7:0] b);
    begin @(negedge clk);txd[c*8 +:8]=b;txv[c]=1;while(!txr[c])@(negedge clk);@(negedge clk);txv[c]=0;end
  endtask
  task automatic watch(input integer c,input [7:0] b,input integer d);
    integer k; begin
      wait(utx[c]===0);repeat(d/2)@(posedge clk);if(utx[c]!==0)$fatal(1,"tx start c%0d",c);
      for(k=0;k<8;k=k+1)begin repeat(d)@(posedge clk);if(utx[c]!==b[k])$fatal(1,"tx data c%0d",c);end
      repeat(d)@(posedge clk);if(utx[c]!==1)$fatal(1,"tx stop c%0d",c);
    end
  endtask
  task automatic drive_rx(input integer c,input [7:0] b,input integer d,input bit good);
    integer k; begin
      @(negedge clk);urx[c]=0;repeat(d)@(negedge clk);
      for(k=0;k<8;k=k+1)begin urx[c]=b[k];repeat(d)@(negedge clk);end
      urx[c]=good;repeat(d)@(negedge clk);urx[c]=1;repeat(d)@(negedge clk);
    end
  endtask
  task automatic take(input integer c,input [7:0] b);
    begin while(!rxv[c])@(negedge clk);if(rxd[c*8 +:8]!==b)$fatal(1,"rx c%0d",c);
      rxready[c]=1;@(negedge clk);rxready[c]=0;end
  endtask
  integer i;
  initial begin
    repeat(4)@(posedge clk);rst_n=1;
    fork put(0,8'h96);watch(0,8'h96,5);put(1,8'h3c);watch(1,8'h3c,7);
         put(2,8'ha5);watch(2,8'ha5,9);put(3,8'h69);watch(3,8'h69,11); join
    drive_rx(1,8'h5a,7,1);take(1,8'h5a);
    drive_rx(2,8'h33,9,0);if(!frame[2]||rxv[2])$fatal(1,"framing");
    for(i=0;i<9;i=i+1)drive_rx(3,i+8'h40,11,1);
    if(!over[3])$fatal(1,"overrun");
    for(i=0;i<8;i=i+1)take(3,i+8'h40);
    @(negedge clk);clr=4'b1100;@(negedge clk);clr=0;
    if(frame[2]||over[3])$fatal(1,"clear");
    fork begin put(0,8'hee);wait(utx[0]===0);repeat(8)@(posedge clk);en[0]=0;
      @(posedge clk);if(utx[0]!==1)$fatal(1,"disable");en[0]=1;end join
    drive_rx(0,8'hc3,5,1);wait(rxv[0]);rst_n=0;#2;
    if(rxv||txr||frame||over||utx!==4'hf)$fatal(1,"async reset");
    $display("HIDDEN_PASS");$finish;
  end
  initial begin #300000;$fatal(1,"timeout");end
endmodule
