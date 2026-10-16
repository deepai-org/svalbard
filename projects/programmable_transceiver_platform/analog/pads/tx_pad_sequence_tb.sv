`timescale 1ns/1ps
module tx_pad_sequence_tb;
 reg clk=0,rst_n=0,supply_ok=0,commit=0,analog_ready=0;
 reg [4:0] request=0;
 wire command_ready,qualified,traffic_ready,buffer_request,fault;
 wire [4:0] active_request;
 pt_tx_pad_sequence #(.PRE_CYCLES(2),.POST_CYCLES(2)) dut(.*);
 always #5 clk=~clk;
 task tick; begin @(posedge clk); #1; end endtask
 task issue(input [4:0] v); begin
  @(negedge clk); if(!command_ready)$fatal(1,"not ready"); request=v;commit=1;
  tick(); @(negedge clk);commit=0;
 end endtask
 initial begin
  #1; rst_n=1;supply_ok=1;
  issue(5'b10011);
  if(qualified || active_request!=0)$fatal(1,"early apply");
  request=5'b00100; // mutate host request while transaction is busy
  tick(); if(active_request!=0)$fatal(1,"short preblank");
  tick(); if(active_request!=5'b10011 || !buffer_request || qualified)$fatal(1,"snapshot/precharge");
  repeat(4)tick(); if(qualified || command_ready)$fatal(1,"ignored readiness");
  analog_ready=1;tick();if(!qualified || command_ready || traffic_ready)$fatal(1,"early traffic ready");
  analog_ready=0;repeat(3)tick();if(!qualified || traffic_ready || fault)$fatal(1,"load settling disabled path");
  analog_ready=1;tick();if(traffic_ready)$fatal(1,"short loaded dwell");
  analog_ready=0;tick();analog_ready=1;tick();if(traffic_ready)$fatal(1,"noncontiguous readiness");
  tick();if(!traffic_ready || !command_ready)$fatal(1,"loaded ready");
  issue(5'b00100);if(qualified || !buffer_request)$fatal(1,"release order");
  tick();tick();if(buffer_request || qualified)$fatal(1,"buffer not released while blanked");
  tick();if(qualified)$fatal(1,"short postblank");tick();if(!qualified)$fatal(1,"TMDS enable");repeat(2)tick();
  issue(5'b00101);repeat(4)tick();if(!fault || qualified || active_request!=0)$fatal(1,"conflict");
  issue(5'b00001);repeat(6)tick();if(fault || !qualified)$fatal(1,"explicit recovery");
  analog_ready=0;tick();if(qualified || !fault)$fatal(1,"readiness loss");
  repeat(4)tick();analog_ready=1;repeat(2)tick();if(qualified)$fatal(1,"automatic rearm");
  issue(5'b10001);repeat(6)tick();if(!qualified)$fatal(1,"rearm");
  #1;supply_ok=0;#1;if(qualified || traffic_ready || buffer_request || active_request!=0)$fatal(1,"async supply disable");
  supply_ok=1;repeat(3)tick();if(qualified)$fatal(1,"supply auto rearm");
  issue(5'b10001);tick();#1;rst_n=0;#1;if(qualified || traffic_ready || buffer_request || active_request!=0)$fatal(1,"reset busy");
  $display("PASS: loaded readiness and contiguous dwell, snapshot, pre/post blanking, readiness, conflict, ordered release, async disable, explicit rearm");$finish;
 end
 initial begin #2000;$fatal(1,"timeout");end
endmodule
