`timescale 1ns/1ps
module tb_control;
 reg rst=1,clk=0,cs=1,mosi=0;wire miso,oe,en,mode,memwr,play,cap;wire[15:0]rf,wi,cl;wire[4:0]idx;wire[23:0]memdata;
 pt_control dut(rst,clk,cs,mosi,miso,oe,16'h1234,en,mode,rf,wi,cl,memwr,idx,memdata,24'habcdef,1'b1,play,cap);
 task transaction(input[7:0]cmd,addr,input[15:0]data,output[15:0]result);
 reg[31:0]send;integer b;begin send={cmd,addr,data};result=0;cs=0;#10;
  for(b=31;b>=0;b=b-1)begin mosi=send[b];#10;clk=1;if(b<16)result={result[14:0],miso};#10;clk=0;end
  #10;cs=1;#10;
 end endtask
 reg[15:0]r;
 initial begin
  #1;cs=0;#1;rst=0;#1;cs=1;#5;rst=1;#10;
  transaction(0,0,0,r);if(r!==16'h5356)$fatal(1,"identity %h",r);
  transaction(8'h80,2,1,r);transaction(0,2,0,r);if(r!=1)$fatal(1,"mode write");
  transaction(8'h80,8'h10,16'h1234,r);transaction(0,8'h10,0,r);if(r!=16'h1234)$fatal(1,"trim write");
  transaction(8'h80,1,1,r);transaction(8'h80,2,0,r);transaction(0,2,0,r);if(r!=1)$fatal(1,"live mode changed");
  transaction(0,4,0,r);if(r!=1)$fatal(1,"live write rejection missing");
  transaction(8'h80,1,0,r);transaction(8'h80,2,0,r);transaction(0,2,0,r);if(r!=0)$fatal(1,"disarmed mode write");
  transaction(0,8'h25,0,r);if(r!=16'hcdef)$fatal(1,"capture read");
  if(oe)$fatal(1,"MISO not tri-stated");
  $display("CONTROL_PASS");$finish;
 end
endmodule
