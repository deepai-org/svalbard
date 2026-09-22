// Decode all five v2 header words at once; detection only, never correction.
// Outputs are zero when invalid. Caller must still gate all effects with good.
module pt_block_header(input wire[49:0]header,input wire mode8,
 input wire[5:0]expected_seq,output wire good,
 output wire[5:0]wire_count,iq_count,output wire[3:0]opcode,
 output wire[7:0]argument);
 reg[29:0]decoded;reg[5:0]syndrome;integer p,d;
 always @*begin
  decoded=0;syndrome=0;d=0;
  for(p=1;p<=36;p=p+1)begin
   if(header[p-1])syndrome=syndrome^6'(p);
   if((p&(p-1))!=0)begin decoded[d]=header[p-1];d=d+1;end
  end
 end
 assign good=header[49:40]==10'h2d3&&header[39:37]==3'b101&&
  syndrome==0&&(^header[36:0])==0&&decoded[17:12]==expected_seq&&
  decoded[5:0]<=(mode8?52:33)&&decoded[11:6]<=(mode8?7:25)&&
  ((decoded[21:18]==0&&decoded[29:22]==0)||
   ((decoded[21:18]==1||decoded[21:18]==2)&&decoded[29:22]<=1));
 assign wire_count=good?decoded[5:0]:6'd0;
 assign iq_count=good?decoded[11:6]:6'd0;
 assign opcode=good?decoded[21:18]:4'd0;
 assign argument=good?decoded[29:22]:8'd0;
endmodule
