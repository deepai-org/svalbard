// Balanced, registered parity tree. The seventh row computes overall parity
// directly from data coefficients, avoiding a second tree over Hamming parity.
// No reset is needed: frame zero is an explicit empty codeword and the first
// publication occurs after a full frame, long after all three stages settle.
// ALIGN=1 (reference model default) delays the data bits by the parity latency so a value that
// changes every clock is encoded consistently. ALIGN=0 omits that 90-bit delay line: valid only
// when value is held for at least three clocks before packet is sampled, as in pt_dense_pair_tx
// (pending/seq settle at the clamp edge, four engine clocks before the publish edge).
module pt_dense_header #(parameter ALIGN=1)(input wire clk,input wire[29:0]value,output reg[39:0]packet);
 function automatic[17:0]row(input[29:0]data,input integer which);
 integer p,d,n,weight,k;begin
  row=0;d=0;n=0;
  for(p=1;p<=36;p=p+1)if((p&(p-1))!=0)begin
   weight=0;for(k=0;k<6;k=k+1)weight=weight+((p>>k)&1);
   if((which<6&&((p>>which)&1)!=0)||(which==6&&(weight%2)==0))begin
    row[n]=data[d];n=n+1;
   end
   d=d+1;
  end
 end endfunction
 reg[41:0]first;reg[13:0]second;reg[6:0]parity;
 wire[29:0]data3;
 genvar r,g;
 generate for(r=0;r<7;r=r+1)begin:rows
  wire[17:0]bits=row(value,r);
  for(g=0;g<6;g=g+1)begin:first_groups
   always @(posedge clk)first[r*6+g]<=^bits[g*3+:3];
  end
  for(g=0;g<2;g=g+1)begin:second_groups
   always @(posedge clk)second[r*2+g]<=^first[r*6+g*3+:3];
  end
  always @(posedge clk)parity[r]<=^second[r*2+:2];
 end endgenerate
 generate if(ALIGN)begin:aligned
  reg[29:0]data1,data2,data_q;
  always @(posedge clk)begin data1<=value;data2<=data1;data_q<=data2;end
  assign data3=data_q;
 end else begin:direct
  assign data3=value;
 end endgenerate
 integer p,d,k;
 always @*begin
  packet=0;d=0;
  for(p=1;p<=36;p=p+1)if((p&(p-1))!=0)begin packet[p-1]=data3[d];d=d+1;end
  for(k=0;k<6;k=k+1)packet[(1<<k)-1]=parity[k];
  packet[36]=parity[6];packet[39:37]=3'b101;
 end
endmodule
