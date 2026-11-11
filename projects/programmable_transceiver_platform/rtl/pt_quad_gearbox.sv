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
// Timing (closure 2026-11-11, rftx 20 ns): in_ready no longer depends on this clock's take (the DAC
// request reached the egress pop / read select through take -> room_after_take). The reservoir is
// 84 bits (21 nibbles) and in_ready = (held <= 44 bits), a REGISTER loaded with the next-state compare:
// a quad is accepted whenever at most 44 bits are held, so the reservoir never holds fewer than one
// sample once primed (44 + 40 = 84 bits max) and one sample per clock is sustained (10 nibbles in per
// accepted quad, 4 or 6 out per sample). out_valid is likewise a register (next held >= width).
module pt_sample_unpack(input wire clk,rst_n,mode8,input wire[39:0]quad,input wire in_valid,
 output wire in_ready,output wire[23:0]sample,output wire out_valid,input wire out_ready);
 reg[83:0]bits;reg[4:0]nibbles;reg rdy,ov;
 wire[4:0]outgoing=mode8?5'd4:5'd6;
 assign out_valid=ov;
 assign in_ready=rdy;
 wire take=ov&&out_ready;
 wire put=in_valid&&rdy;
 wire[4:0]remaining=nibbles-(take?outgoing:5'd0);
 wire[4:0]nibbles_n=remaining+(put?5'd10:5'd0);
 wire[83:0]shifted=mode8?bits>>16:bits>>24;
 wire[83:0]base_bits=take?shifted:bits;
 reg[83:0]aligned;
 always @*begin aligned=84'd0;if(put)aligned=84'(quad)<<(4*remaining);end
 assign sample=mode8?{8'd0,bits[15:0]}:bits[23:0];
`ifdef FORMAL
 reg f_past=0;
 always @(posedge clk)f_past<=1;
 always @*if(!f_past)assume(!rst_n);
 always @*if(f_past&&rst_n)begin
  assert(nibbles<=5'd21);
  assert((bits>>(4*nibbles))==0);
  assert(rdy==(nibbles<=5'd11));
  assert(ov==(nibbles>=outgoing));
 end
 // mode8 is static while out of reset
 always @(posedge clk)if(f_past&&rst_n)assume($stable(mode8));
`endif
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin bits<=0;nibbles<=0;rdy<=1'b1;ov<=1'b0;end
  else begin
   if(take||put)bits<=base_bits|aligned;
   nibbles<=nibbles_n;
   rdy<=nibbles_n<=5'd11;
   ov<=nibbles_n>=outgoing;
  end
 end
endmodule
