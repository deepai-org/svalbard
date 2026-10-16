`timescale 1ns/1ps
module replay;
reg clk=0,rst_n=1,supply_ok=1,commit=0;reg measured_ready=0;
reg[4:0]request=0;
wire command_ready,qualified,traffic_ready,buffer_request,fault;wire[4:0]active_request;
wire analog_ready=active_request[4] ? measured_ready : 1'b1;
pt_tx_pad_sequence #(.PRE_CYCLES(2),.POST_CYCLES(2)) dut(.*);
always #2 clk=~clk;
initial begin
 $monitor("TRACE %0.3f %0d %0d %0d %0d %0d",$realtime,active_request,qualified,buffer_request,rst_n,traffic_ready);
 #0.01;rst_n=0;#0.09;rst_n=1;
 #3.9;request=4;commit=1;#4;commit=0;
 #23;rst_n=0;#0.5;rst_n=1;
 #0.5;supply_ok=0;#20.2;supply_ok=1;
 send(17,70);send(19,140);send(8,200);send(0,240);
end
task send(input [4:0] value,input integer earliest_ns);
 begin
  if($realtime<earliest_ns) #(earliest_ns-$realtime);
  wait(command_ready);@(negedge clk);request=value;commit=1;
  @(negedge clk);commit=0;
 end
endtask
initial begin #300;$finish;end
initial begin
#1;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=1;
#4;measured_ready=1;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=1;
#4;measured_ready=1;
#4;measured_ready=1;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=1;
#4;measured_ready=1;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=1;
#4;measured_ready=1;
#4;measured_ready=1;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
#4;measured_ready=0;
end
always @(posedge clk) if(commit && !command_ready) $display("BUSY_COMMIT %0.3f",$realtime);
endmodule
