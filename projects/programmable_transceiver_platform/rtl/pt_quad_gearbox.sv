// Ordered LSB-first conversion between RF samples and 40-bit transport quads
// (AC-1). Both converters live in the RF sample-clock domains, next to the
// converters: the CDC FIFOs then carry quads for both payload owners, and
// one sample moves per sample clock (40 MS/s) at any host rate, including the
// reduced div2 rate that RF modes use (spec AC-4 PWR-HOST-RF).
// mode8: a sample is 16 bits (compressed {I[11:4], Q[11:4]}), else 24 bits.

// Sample -> quad. One sample in per valid clock, no backpressure: a quad is
// emitted whenever ten nibbles are held (at most every clock), so the
// reservoir never holds more than 9 + 6 = 15 nibbles.
// flush (fast gain commit, opcode4): the reservoir is discarded after this clock's push (a complete
// quad still goes out); `base` is the number of nibbles discarded.
module pt_sample_pack(input wire clk,rst_n,mode8,input wire[23:0]sample,input wire valid,
 output wire[39:0]quad,output wire push,input wire flush,output wire[3:0]base);
 reg[59:0]bits;reg[3:0]nibbles;
 wire[3:0]incoming=mode8?4'd4:4'd6;
 assign push=nibbles>=4'd10;
 assign quad=bits[39:0];
 assign base=push?nibbles-4'd10:nibbles;     // 0..9
 wire[23:0]value=mode8?{8'd0,sample[15:0]}:sample;
 wire[59:0]kept=push?{40'd0,bits[59:40]}:bits;
 reg[59:0]appended;
 always @*case(base)
  4'd0:appended=60'(value);       4'd1:appended=60'(value)<<4;
  4'd2:appended=60'(value)<<8;    4'd3:appended=60'(value)<<12;
  4'd4:appended=60'(value)<<16;   4'd5:appended=60'(value)<<20;
  4'd6:appended=60'(value)<<24;   4'd7:appended=60'(value)<<28;
  4'd8:appended=60'(value)<<32;   default:appended=60'(value)<<36;
 endcase
`ifdef FORMAL
 reg f_past=0;
 always @(posedge clk)f_past<=1;
 always @*if(!f_past)assume(!rst_n);
 always @*if(f_past)begin
  assert(nibbles<=4'd15);
  assert((bits>>(4*nibbles))==0);
  if(valid)assert((kept|appended)==(kept|(60'(value)<<(4*base))));
 end
`endif
 always @(posedge clk or negedge rst_n)
  if(!rst_n)begin bits<=0;nibbles<=0;end
  else begin
   bits<=flush?60'd0:kept|(valid?appended:60'd0);
   nibbles<=flush?4'd0:nibbles-(push?4'd10:4'd0)+(valid?incoming:4'd0);
  end
endmodule

// Quad -> sample. One sample out per accepted request; a quad is taken from
// the FWFT source when no more than five nibbles remain after this clock's
// output (reservoir <= 15 nibbles). Ready is decoded from the registered
// occupancy before the late request.
module pt_sample_unpack(input wire clk,rst_n,mode8,input wire[39:0]quad,input wire in_valid,
 output wire in_ready,output wire[23:0]sample,output wire out_valid,input wire out_ready);
 reg[59:0]bits;reg[3:0]nibbles;
 wire[3:0]outgoing=mode8?4'd4:4'd6;
 assign out_valid=nibbles>=outgoing;
 wire take=out_valid&&out_ready;
 wire room_now=nibbles<=4'd5;
 wire room_after_take=nibbles<=(mode8?4'd9:4'd11);
 assign in_ready=room_now||(take&&room_after_take);
 wire put=in_valid&&in_ready;
 wire[59:0]shifted=mode8?bits>>16:bits>>24;
 function automatic[59:0]aligned(input[3:0]offset,input[39:0]value);
  begin case(offset)
   4'd0:aligned=60'(value);    4'd1:aligned=60'(value)<<4;  4'd2:aligned=60'(value)<<8;
   4'd3:aligned=60'(value)<<12;4'd4:aligned=60'(value)<<16; default:aligned=60'(value)<<20;
  endcase end
 endfunction
 wire[59:0]after_take=shifted|((in_valid&&room_after_take)?aligned(nibbles-outgoing,quad):60'd0);
 wire[59:0]without_take=bits|((in_valid&&room_now)?aligned(nibbles,quad):60'd0);
 assign sample=mode8?{8'd0,bits[15:0]}:bits[23:0];
`ifdef FORMAL
 // Compare the factored implementation with ordered reservoir arithmetic
 // for every reachable occupancy, data pattern, mode and transfer case.
 reg f_past=0;
 always @(posedge clk)f_past<=1;
 always @*if(!f_past)assume(!rst_n);
 wire[3:0]reference_remaining=nibbles-(take?outgoing:4'd0);
 wire reference_ready=reference_remaining<=4'd5;
 wire[59:0]reference_next=(take?shifted:bits)|
     ((in_valid&&reference_ready)?(60'(quad)<<(4*reference_remaining)):60'd0);
 always @*if(f_past)begin
  assert(nibbles<=4'd15);
  assert((bits>>(4*nibbles))==0);
  assert(in_ready==reference_ready);
  if(take||put)assert((take?after_take:without_take)==reference_next);
 end
`endif
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin bits<=0;nibbles<=0;end
  else begin
   if(take||put)bits<=take?after_take:without_take;
   nibbles<=nibbles-(take?outgoing:4'd0)+(put?4'd10:4'd0);
  end
 end
endmodule
