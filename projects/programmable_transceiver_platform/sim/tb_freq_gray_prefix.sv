`timescale 1ns/1ps
module tb_freq_gray_prefix;
 wire locked_ref,locked,lost;wire[13:0]diff;wire[15:0]count;
 pt_freq_count dut(1'b0,3'd0,2'd0,3'd0,2'd0,16'd0,6'd0,1'b0,1'b0,
  locked_ref,locked,lost,diff,count,1'b0);
 integer value;reg[17:0]gray;
 initial begin
  for(value=0;value<(1<<18);value=value+1)begin
   gray=18'(value^(value>>1));
   if(dut.g2b(gray)!==18'(value))$fatal(1,"Gray conversion mismatch %h",gray);
  end
  $display("FREQ_GRAY_PREFIX_PASS 262144 exhaustive 18-bit values");$finish;
 end
endmodule
