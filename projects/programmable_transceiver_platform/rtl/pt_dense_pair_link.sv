// Finite training acquisition in either ten-bit phase of a twenty-bit
// capture stream. Once locked, alignment is fixed until reset. Searching
// payload for training would permit accidental live-data reacquisition.
module pt_dense_pair_link_rx(input wire clk,rst_n,payload_iq,
 input wire[19:0]in_pair,input wire wire_ready,iq_ready,
 output wire[19:0]data,output wire[1:0]wire_count,iq_count,
 output wire command_valid,fault,output reg locked,
 output wire[3:0]opcode,output wire[7:0]argument);
 reg[1:0]aligned_match,shifted_match;
 reg[9:0]previous_high;
 reg[8:0]wait_count;
 reg shifted,acquisition_fault;
 wire[19:0]shifted_pair={in_pair[9:0],previous_high};
 function automatic[19:0]training(input[1:0]index);
 begin case(index)
  0:training={10'h05a,10'h3a5};1:training={10'h12c,10'h2d3};
  2:training={10'h096,10'h369};3:training={10'h1e1,10'h21e};
 endcase end endfunction
 wire aligned_ok=in_pair==training(aligned_match);
 wire shifted_ok=shifted_pair==training(shifted_match);
 wire payload_fault;
 assign fault=acquisition_fault||payload_fault;
 pt_dense_pair_rx payload(clk,rst_n&&locked,payload_iq,
  shifted?shifted_pair:in_pair,wire_ready,iq_ready,data,wire_count,iq_count,
  command_valid,payload_fault,opcode,argument);
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   aligned_match<=0;shifted_match<=0;previous_high<=0;wait_count<=0;
   shifted<=0;acquisition_fault<=0;locked<=0;
  end else begin
   previous_high<=in_pair[19:10];
   if(!locked&&!acquisition_fault)begin
    if(aligned_ok&&aligned_match==3)begin locked<=1;shifted<=0;end
    else if(shifted_ok&&shifted_match==3)begin locked<=1;shifted<=1;end
    else if(wait_count==511)acquisition_fault<=1;
    else begin
     wait_count<=wait_count+1'b1;
     aligned_match<=aligned_ok?aligned_match+1'b1:in_pair==training(0)?2'd1:2'd0;
     shifted_match<=shifted_ok?shifted_match+1'b1:shifted_pair==training(0)?2'd1:2'd0;
    end
   end
  end
 end

endmodule

// Related-clock boundary for a 312.5 MHz ten-bit word port and a 156.25 MHz
// paired engine. A pair register gives the engine a whole pair period,
// then a word-clock register launches each low/high word. Constrain
// pair_clk as a divide-by-two generated clock during STA; the extra pair
// stage keeps all engine logic off the fast word-register input paths.
// Local phase flops drive one word bit each. Preserve these small physical
// drivers across synthesis rather than rebuilding one high-fanout phase net.
`ifndef FORMAL
(* keep_hierarchy = "yes" *)
`endif
module pt_word_phase(input wire clk,rst_n,output reg phase);
 always @(posedge clk or negedge rst_n)
  if(!rst_n)phase<=1;else phase<=!phase;
endmodule

module pt_pair_word_boundary(input wire word_clk,rst_n,
 input wire[19:0]tx_pair,output reg[9:0]tx_word,
 input wire[9:0]rx_word,output reg[19:0]rx_pair,
 output wire pair_clk);
 reg half;
 (* async_reg="true" *) reg[1:0]reset_release;
 always @(posedge word_clk or negedge rst_n)
  if(!rst_n)reset_release<=0;else reset_release<={reset_release[0],1'b1};
 wire local_rst_n=reset_release[1];
 wire[9:0]word_phase;
 genvar bit_index;
 generate for(bit_index=0;bit_index<10;bit_index=bit_index+1)begin:phase_bits
  pt_word_phase phase_driver(word_clk,local_rst_n,word_phase[bit_index]);
 end endgenerate
 reg[9:0]tx_high,rx_first;
 reg[19:0]launch_pair;
 // Keep the divider's local feedback ahead of the generated-clock tree.
 // Otherwise CTS can route its feedback through the entire engine tree,
 // adding that insertion delay to the fast divide-by-two recurrence.
`ifdef SYNTHESIS
 (* keep=1, dont_touch=1 *) gf180mcu_fd_sc_mcu7t5v0__buf_4 pair_clock_buffer(.I(half),.Z(pair_clk));
`else
 assign pair_clk=half;
`endif
 always @(posedge pair_clk or negedge local_rst_n)
  if(!local_rst_n)launch_pair<=0;else launch_pair<=tx_pair;
 integer bit_number;
 always @(posedge word_clk or negedge local_rst_n)begin
  if(!local_rst_n)begin half<=0;tx_high<=0;tx_word<=0;rx_first<=0;rx_pair<=0;end
  else begin
   half<=!half;
   // Pipeline the word select separately from the divider's clock load.
   // Low/high launch uses the pair from the preceding pair-clock edge.
   // Both word edges retain their own 3.2 ns register path. Only the
   // launch_pair -> enabled low-word capture has a two-word setup window.
   for(bit_number=0;bit_number<10;bit_number=bit_number+1)begin
    if(word_phase[bit_number])begin
     tx_word[bit_number]<=launch_pair[bit_number];
     tx_high[bit_number]<=launch_pair[bit_number+10];
    end else tx_word[bit_number]<=tx_high[bit_number];
    // Complete a receive pair on the opposite fast edge, before the next
    // pair-clock rise. Local phase drivers keep this mux fanout bounded.
    if(word_phase[bit_number])rx_first[bit_number]<=rx_word[bit_number];
    else begin
     rx_pair[bit_number]<=rx_first[bit_number];
     rx_pair[bit_number+10]<=rx_word[bit_number];
    end
   end
  end
 end
`ifdef FORMAL
 reg f_past_valid=0;
 initial assume(!rst_n);
 always @(posedge word_clk or negedge rst_n)
  if(!rst_n)f_past_valid<=0;else f_past_valid<=1;
 always @(posedge word_clk)begin
  if(f_past_valid&&rst_n&&$past(rst_n))begin
   assert(word_phase=={10{!half}});
   if($past(word_phase[0]))begin
    assert(tx_word==$past(launch_pair[9:0]));
    assert(tx_high==$past(launch_pair[19:10]));
   end else begin
    assert(tx_word==$past(tx_high));
    assert(tx_high==$past(tx_high));
   end
   // The slow register changes only after the enabled capture edge and
   // is stable for the entire intervening fast cycle before capture.
   if(word_phase[0])assert(launch_pair==$past(launch_pair));
   cover(word_phase[0]&&tx_word!=0);
   cover(!word_phase[0]&&tx_word!=0);
  end
 end
`endif
endmodule

`ifdef SYNTHESIS
// The GF180 Liberty/LEF/GDS supplies the implementation during hardening.
(* blackbox *) module gf180mcu_fd_sc_mcu7t5v0__buf_4(input wire I,output wire Z);
endmodule
`endif
