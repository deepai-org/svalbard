// Bit order matches transport_model.py: sample LSB first across 10-bit words.
module pt_pack(input wire clk,rst_n,mode8,input wire[23:0]sample,
 input wire sample_valid,output wire sample_ready,
 output wire[9:0]word,output wire word_valid,input wire word_ready);
 reg[23:0]held_sample;reg held_valid;
 reg[47:0]bits;reg[5:0]count;
 wire[5:0]width=mode8?16:24;
 assign word=bits[9:0];assign word_valid=count>=10;
 // Deliberately serialize reservoir insertion/removal; rate headroom checked in simulation.
 wire insert=held_valid&&count<10;
 assign sample_ready=!held_valid||count<10;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin bits<=0;count<=0;held_sample<=0;held_valid<=0;end
  else begin
   if(sample_ready)begin held_valid<=sample_valid;if(sample_valid)held_sample<=sample;end
   if(word_valid&&word_ready)begin bits<=bits>>10;count<=count-10;end
  else if(insert)begin
   bits<=bits|(({24'b0,held_sample}&(mode8?48'hffff:48'hffffff))<<count);count<=count+width;
  end
  end
 end
endmodule
module pt_unpack(input wire clk,rst_n,mode8,input wire[9:0]word,input wire word_valid,
 output wire word_ready,output wire[23:0]sample,output wire sample_valid,input wire sample_ready);
 reg[47:0]bits;reg[5:0]count;wire[5:0]width=mode8?16:24;
 assign sample=mode8?{8'b0,bits[15:0]}:bits[23:0];assign sample_valid=count>=width;
 assign word_ready=count<width;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin bits<=0;count<=0;end
  else if(sample_valid&&sample_ready)begin bits<=bits>>width;count<=count-width;end
  else if(word_valid&&word_ready)begin bits<=bits|({38'b0,word}<<count);count<=count+10;end
 end
endmodule
