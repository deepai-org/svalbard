// Aligned v2 TX with retained snapshot staging. First frame is empty.
module pt_stream_tx(input wire clk,rst_n,mode8,
 input wire[9:0]wire_data,iq_data,input wire[6:0]wire_count,input wire[5:0]iq_count,
 input wire[3:0]opcode,input wire[7:0]argument,
 output wire wire_pop,iq_pop,output reg[9:0]out_word);
 `include "pt_schedule.vh"
 // Delay bank commit one cycle; capture address before active/pos advance.
 reg stage_valid;reg[6:0]stage_address;reg[9:0]stage_data;
 reg[9:0]banks[0:127];reg active;reg[5:0]pos,seq;
 reg[5:0]wc[0:1],qc[0:1];reg[5:0]leftw,leftq;reg[11:0]command[0:1];
 // Decode the following word's owner one cycle ahead; mode is frozen while armed.
 reg[1:0]own;
 wire[29:0]header={command[active][7:0],command[active][11:8],seq,qc[active],wc[active]};
 function automatic[39:0]protect(input[29:0]value);
 reg[36:0]code;integer p,d,k;reg parity;
 begin
  code=0;d=0;
  for(p=1;p<=36;p=p+1)if((p&(p-1))!=0)begin code[p-1]=value[d];d=d+1;end
  for(k=0;k<6;k=k+1)begin
   parity=0;
   for(p=1;p<=36;p=p+1)if((p&(1<<k))!=0)parity=parity^code[p-1];
   code[(1<<k)-1]=parity;
  end
  code[36]=^code[35:0];protect={3'b101,code};
 end endfunction
 wire[39:0]protected_header=protect(header);
 assign wire_pop=own==1&&leftw!=0;
 assign iq_pop=own==2&&leftq!=0;
 always @* begin
  out_word=0;
  case(pos)
   0:out_word=protected_header[9:0];1:out_word=protected_header[19:10];
   2:out_word=protected_header[29:20];3:out_word=protected_header[39:30];
   4:out_word=10'h2d3;
   default:out_word=banks[{active,pos}];
  endcase
 end
 integer j;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin own<=0;stage_valid<=0;stage_address<=0;stage_data<=0;active<=0;pos<=0;seq<=0;command[0]<=0;command[1]<=0;leftw<=0;leftq<=0;wc[0]<=0;wc[1]<=0;qc[0]<=0;qc[1]<=0;
   for(j=0;j<128;j=j+1)banks[j]<=0;
  end else begin
   own<=owner(mode8,pos-6'd1);
   if(stage_valid)banks[stage_address]<=stage_data;
   stage_valid<=pos>=5;
   if(pos==0)begin
    command[!active]<={opcode,argument};
    wc[!active]<=wire_count>(mode8?52:33)?(mode8?52:33):wire_count;
    qc[!active]<=iq_count>(mode8?7:25)?(mode8?7:25):iq_count;
    leftw<=wire_count>(mode8?52:33)?(mode8?52:33):wire_count;
    leftq<=iq_count>(mode8?7:25)?(mode8?7:25):iq_count;
   end
   if(pos>=5)begin
    stage_address<={!active,pos};
    stage_data<=wire_pop?wire_data:iq_pop?iq_data:10'b0;
    if(wire_pop)leftw<=leftw-1'b1;if(iq_pop)leftq<=leftq-1'b1;
   end
   if(pos==63)begin active<=!active;seq<=seq+1'b1;end
   pos<=pos+1'b1;
  end
 end
endmodule
