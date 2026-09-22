module crc_equivalence(input wire[15:0]old,input wire[9:0]w,output wire equal);
 `include "pt_crc.vh"
 reg[15:0]reference;integer k;
 always @*begin
  reference=old;
  for(k=9;k>=0;k=k-1)
   reference={reference[14:0],1'b0}^((reference[15]^w[k])?16'h1021:16'h0);
 end
 assign equal=step(old,w)==reference;
endmodule
