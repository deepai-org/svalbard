`timescale 1ns/1ps
// Executable ideal AFE boundaries, NOT synthesizable circuits or performance evidence.
// Clocks are supplied by the testbench: this does not model CDR acquisition or PLL noise.
module pt_wire_afe_model(input wire rst_n,bit_clk,tx_idle,
 input wire[9:0]tx_word,input wire tx_valid,
 output reg tx_p,output wire tx_n,input wire rx_p,
 output reg[9:0]rx_word,output reg rx_valid,output reg word_clk);
 reg[3:0]position;reg[9:0]tx_shift,rx_shift;
 assign tx_n=~tx_p;
 always @(posedge bit_clk or negedge rst_n)begin
  if(!rst_n)begin position<=0;tx_shift<=0;rx_shift<=0;tx_p<=0;rx_word<=0;rx_valid<=0;word_clk<=0;end
  else begin
   rx_shift<={rx_p,rx_shift[9:1]};rx_valid<=0;
   if(position==0)begin tx_shift<=tx_word>>1;tx_p<=tx_valid&&!tx_idle?tx_word[0]:0;word_clk<=0;end
   else begin tx_p<=tx_idle?0:tx_shift[0];tx_shift<=tx_shift>>1;end
   if(position==9)begin rx_word<={rx_p,rx_shift[9:1]};rx_valid<=1;word_clk<=1;position<=0;end
   else position<=position+1'b1;
  end
 end
endmodule

// Signed normalized baseband interface. ADC/DAC saturation is explicit.
// RF LNA/mixer/filter, converter ENOB, LO and impedance are deliberately not inferred.
module pt_converter_model(input wire sample_clk,rst_n,mute,
 input real rx_i,rx_q,input wire[23:0]tx_sample,
 output reg[23:0]rx_sample,output real tx_i,tx_q);
 function automatic [11:0] quantize(input real x);
 integer v;begin v=$rtoi(x*2048.0);if(v>2047)v=2047;if(v< -2048)v=-2048;quantize=v;end endfunction
 assign tx_i=mute?0.0:$itor($signed(tx_sample[11:0]))/2048.0;
 assign tx_q=mute?0.0:$itor($signed(tx_sample[23:12]))/2048.0;
 always @(posedge sample_clk or negedge rst_n)
  if(!rst_n)rx_sample<=0;else rx_sample<={quantize(rx_q),quantize(rx_i)};
endmodule
