// Startup on an already word-aligned link. Receiver must be armed before TX
// sends its finite preamble. No live-data scanning/reacquisition after lock.
module pt_stream_link_tx(input wire clk,rst_n,mode8,
 input wire[9:0]wire_data,iq_data,input wire[6:0]wire_count,input wire[5:0]iq_count,
 input wire[3:0]opcode,input wire[7:0]argument,
 output wire wire_pop,iq_pop,output reg[9:0]out_word);
 reg[3:0]training;wire running=training==8;
 wire[9:0]payload_word;wire wp,qp;
 pt_stream_tx payload(clk,rst_n&&running,mode8,wire_data,iq_data,wire_count,iq_count,opcode,argument,wp,qp,payload_word);
 assign wire_pop=running&&wp;assign iq_pop=running&&qp;
 always @(posedge clk or negedge rst_n)
  if(!rst_n)training<=0;else if(!running)training<=training+1'b1;
 always @*case(training)
  0:out_word=10'h3a5;1:out_word=10'h05a;2:out_word=10'h2d3;3:out_word=10'h12c;
  4:out_word=10'h369;5:out_word=10'h096;6:out_word=10'h21e;7:out_word=10'h1e1;
  default:out_word=payload_word;
 endcase
endmodule

module pt_stream_link_rx(input wire clk,rst_n,mode8,input wire[9:0]in_word,
 input wire wire_ready,iq_ready,output wire[9:0]data,
 output wire wire_valid,iq_valid,command_valid,fault,output reg locked,
 output wire[3:0]opcode,output wire[7:0]argument);
 reg[2:0]matched;reg[9:0]wait_count;reg acquisition_fault;
 wire payload_fault;reg[9:0]expected;
 assign fault=acquisition_fault||payload_fault;
 pt_stream_rx payload(clk,rst_n&&locked,mode8,in_word,wire_ready,iq_ready,data,wire_valid,iq_valid,command_valid,payload_fault,opcode,argument);
 always @*case(matched)
  0:expected=10'h3a5;1:expected=10'h05a;2:expected=10'h2d3;3:expected=10'h12c;
  4:expected=10'h369;5:expected=10'h096;6:expected=10'h21e;7:expected=10'h1e1;
 endcase
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin matched<=0;wait_count<=0;acquisition_fault<=0;locked<=0;end
  else if(!locked&&!acquisition_fault)begin
   // A complete prefix on the deadline wins over timeout.
   if(in_word==expected&&matched==7)begin locked<=1;matched<=0;end
   else if(wait_count==1023)acquisition_fault<=1;
   else begin
    wait_count<=wait_count+1'b1;
    if(in_word==expected)matched<=matched+1'b1;
    else matched<=(in_word==10'h3a5)?3'd1:3'd0;
   end
  end
 end
endmodule
