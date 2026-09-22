module pt_prbs #(parameter [30:0] SEED=31'h7fffffff)(input wire clk,rst_n,step,
 output wire[9:0]word);
 reg[30:0]state;reg[30:0]next_state;reg[9:0]value;integer k;
 always @*begin next_state=state;value=0;
  for(k=0;k<10;k=k+1)begin value[k]=next_state[30];next_state={next_state[29:0],next_state[30]^next_state[27]};end
 end
 assign word=value;
 always @(posedge clk or negedge rst_n)if(!rst_n)state<=SEED==0?31'b1:SEED;else if(step)state<=next_state;
endmodule

// Generic successive-approximation calibration helper. Caller guarantees a quiet window.
module pt_calibrator(input wire clk,rst_n,start,input wire above_target,
 output reg[11:0]trial,output reg busy,done);
 reg[3:0]bitpos;reg[3:0]settle;reg[11:0]accepted;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin trial<=0;busy<=0;done<=0;bitpos<=0;settle<=0;accepted<=0;end
  else if(start&&!busy&&!done)begin trial<=12'h800;accepted<=0;bitpos<=11;settle<=8;busy<=1;end
  else if(busy)begin
   if(settle!=0)settle<=settle-1'b1;
   else if(bitpos==0)begin trial<=above_target?accepted:trial;done<=1;busy<=0;end
   else begin
    if(!above_target)accepted<=trial;
    trial<=(above_target?accepted:trial)|(12'b1<<(bitpos-1'b1));bitpos<=bitpos-1'b1;settle<=8;
   end
  end else if(!start)done<=0;
 end
endmodule
