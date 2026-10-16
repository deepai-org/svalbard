`timescale 1ns/1ps
module replay;
reg clk=0,rst_n=1,supply_ok=1,commit=0,analog_ready=1;
reg[4:0]request=0;
wire command_ready,qualified,buffer_request,fault;wire[4:0]active_request;
pt_tx_pad_sequence #(.PRE_CYCLES(2),.POST_CYCLES(2)) dut(.*);
always #2 clk=~clk;
initial begin
 $monitor("TRACE %0.3f %0d %0d %0d %0d",$realtime,active_request,qualified,buffer_request,rst_n);
 #0.01;rst_n=0;#0.09;rst_n=1;
 #3.9;request=4;commit=1;#4;commit=0;
 #18;rst_n=0;#5;rst_n=1;
 #1;supply_ok=0;#20.2;supply_ok=1;analog_ready=0;
 #17.8;request=17;commit=1;#4;commit=0;
 #36;analog_ready=1;
 #30;request=19;commit=1;#4;commit=0;
 #56;request=8;commit=1;#4;commit=0;
 #36;request=0;commit=1;#4;commit=0;
 #56;$finish;
end
endmodule
