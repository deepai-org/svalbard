`timescale 1ns/1ps
module tb_dense_pair_link;
 reg wc=0,rc=0,tx_rst=1,rx_rst=1,owner=0;
 real phase;integer capture_offset;
 wire tc,rpc;wire[19:0]tx_pair,rx_pair,data,unused_pair;
 wire[9:0]word,unused_word;wire wp,qp,cv,fault,locked;
 wire[1:0]wcount,qcount;wire[3:0]opcode;wire[7:0]argument;
 integer source_pair=0,received=0,commands=0,cycles=0,fo;
 function automatic[9:0]sample(input integer index);begin sample=(index*37+19)%1024;end endfunction
 wire[19:0]source={sample(2*source_pair+1),sample(2*source_pair)};
 pt_pair_word_boundary launch(wc,tx_rst,tx_pair,word,10'd0,unused_pair,tc);
 pt_pair_word_boundary capture(rc,rx_rst,20'd0,unused_word,word,rx_pair,rpc);
 pt_dense_pair_link_tx tx(tc,tx_rst,owner,source,source,7'd64,7'd64,4'd0,8'd0,wp,qp,tx_pair);
 pt_dense_pair_link_rx rx(rpc,rx_rst,owner,rx_pair,1'b1,1'b1,data,wcount,qcount,cv,fault,locked,opcode,argument);
 always #1.6 wc=~wc;
 initial begin
  if(!$value$plusargs("PHASE=%f",phase))phase=0.8;
  if(!$value$plusargs("OFFSET=%d",capture_offset))capture_offset=0;
  if(!$value$plusargs("OWNER=%d",owner))owner=0;
  #(phase);forever #1.6 rc=~rc;
 end
 always @(posedge tc)if(tx_rst)begin
  if((owner&&wp)||(!owner&&qp))$fatal(1,"Inactive source popped");
  if(wp||qp)source_pair<=source_pair+1;
 end
 always @(posedge rpc)if(rx_rst)begin
  cycles=cycles+1;
  if($test$plusargs("TRACE")&&cycles<32)$display("RX %t %h locked=%b",$time,rx_pair,locked);
  if(fault)$fatal(1,"Paired link fault, phase=%f offset=%d owner=%d",phase,capture_offset,owner);
  if((owner&&wcount)||(!owner&&qcount))$fatal(1,"Inactive destination accepted");
  if(cv)begin
   if(opcode||argument)$fatal(1,"Incorrect command");
   commands=commands+1;
  end
  if(wcount||qcount)begin
   if(data[9:0]!==sample(received))$fatal(1,"First payload mismatch at %d",received);
   received=received+1;
   if(wcount==2||qcount==2)begin
    if(data[19:10]!==sample(received))$fatal(1,"Second payload mismatch at %d",received);
    received=received+1;
   end
  end
  if(commands==200)begin
   if(!locked||received<11000)$fatal(1,"Insufficient link traffic");
   fo=$fopen("result.txt","w");$fwrite(fo,"%d %d %d\n",received,commands,source_pair);$fclose(fo);
   $display("PASS paired word boundary: %d words %d frames",received,commands);$finish;
  end
  if(cycles>7000)$fatal(1,"Link failed to acquire/progress");
 end
 initial begin
  #0.1;tx_rst=0;rx_rst=0;
  #(1.9+capture_offset*3.2);rx_rst=1;
  #(40.0-2.0-capture_offset*3.2);tx_rst=1;
 end
 initial begin #50000;$fatal(1,"Paired boundary timeout");end
endmodule
