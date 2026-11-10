// Ordered LSB-first conversion between 20-bit transport pairs and 16/24-bit
// samples. Both widths are whole nibbles, so a small constant-shift mux
// replaces the general bit-count barrel shifter. Simultaneous transfer in
// both directions sustains the 156.25 MHz pair engine's service rate.
module pt_pair_gearbox #(parameter PACK=1)(input wire clk,rst_n,mode8,
 input wire[23:0]din,input wire in_valid,output wire in_ready,
 output wire[23:0]dout,output wire out_valid,input wire out_ready);
 reg[39:0]bits;
 reg[3:0]nibbles;
 wire[3:0]incoming=PACK?(mode8?4:6):5;
 wire[3:0]outgoing=PACK?5:(mode8?4:6);
 assign out_valid=nibbles>=outgoing;
 wire take=out_valid&&out_ready;
 // Decode space before the late downstream-ready signal arrives. Computing
 // a conditional subtraction first chained egress-full through alignment,
 // frame readiness and the next queue's memory input.
 wire room_now=PACK?(nibbles<=(mode8?6:4)):(nibbles<=5);
 wire room_after_take=PACK?(nibbles<=(mode8?11:9)):(nibbles<=(mode8?9:11));
 assign in_ready=room_now||(take&&room_after_take);
 wire put=in_valid&&in_ready;
 wire[23:0]input_bits=PACK?(mode8?{8'd0,din[15:0]}:din):{4'd0,din[19:0]};
 function automatic[39:0]aligned(input[3:0]offset,input[23:0]value);
  begin case(offset)
   0:aligned={16'd0,value};1:aligned={12'd0,value,4'd0};
   2:aligned={8'd0,value,8'd0};3:aligned={4'd0,value,12'd0};
   4:aligned={value,16'd0};5:aligned={value[19:0],20'd0};
   6:aligned={value[15:0],24'd0};default:aligned=0;
  endcase end
 endfunction
 wire[39:0]after_take=(PACK?bits>>20:mode8?bits>>16:bits>>24)|
                         ((in_valid&&room_after_take)?aligned(nibbles-outgoing,input_bits):40'd0);
 wire[39:0]without_take=bits|((in_valid&&room_now)?aligned(nibbles,input_bits):40'd0);
`ifdef FORMAL
 // Compare the factored implementation with ordered reservoir arithmetic
 // for every valid occupancy, data pattern, mode and transfer combination.
 wire[3:0]reference_remaining=nibbles-(take?outgoing:4'd0);
 wire reference_ready=reference_remaining<=10-incoming;
 wire[39:0]reference_next=(take?(PACK?bits>>20:mode8?bits>>16:bits>>24):bits)|
                         ((in_valid&&reference_ready)?(40'(input_bits)<<(4*reference_remaining)):40'd0);
 always @*if(nibbles<=10)begin
  assert(in_ready==reference_ready);
  if(take||put)assert((take?after_take:without_take)==reference_next);
 end
`endif
 assign dout=PACK?{4'd0,bits[19:0]}:mode8?{8'd0,bits[15:0]}:bits[23:0];
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin bits<=0;nibbles<=0;end
  else begin
   if(take||put)bits<=take?after_take:without_take;
   case({put,take})
    2'b10:nibbles<=nibbles+incoming;
    2'b01:nibbles<=nibbles-outgoing;
    2'b11:nibbles<=PACK?(mode8?nibbles-1'b1:nibbles+1'b1):
                                 (mode8?nibbles+1'b1:nibbles-1'b1);
    default:begin end
   endcase
  end
 end
endmodule

// Reconstitute a contiguous pair stream after headers with odd payload
// counts. ready must reserve space for at most one complete output pair.
module pt_pair_collect(input wire clk,rst_n,input wire[19:0]data,
 input wire[1:0]count,output wire[19:0]pair,output wire push);
 reg[9:0]first;reg have_first;
 assign push=count==2||(count==1&&have_first);
 assign pair=have_first?{data[9:0],first}:data;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin first<=0;have_first<=0;end
  else case(count)
   1:begin if(!have_first)first<=data[9:0];have_first<=!have_first;end
   2:if(have_first)first<=data[19:10];
   default:begin end
  endcase
 end
endmodule
