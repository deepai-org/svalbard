// PRBS generation moved to rtl/pt_pattern.sv (pt_pattern_gen/pt_pattern_check, consolidation P2-6).

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
