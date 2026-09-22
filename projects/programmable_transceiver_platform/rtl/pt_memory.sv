// Separate capture/playback banks. Configuration writes allowed only while disarmed.
module pt_memory(input wire rst_n,spi_clk,memory_write,input wire[4:0]index,
 input wire[23:0]memory_wdata,output wire[23:0]capture_data,
 input wire rf_rx_clk,rf_tx_clk,capture_enable,playback_enable,
 input wire[23:0]sample,input wire sample_valid,output reg capture_done,
 output wire[23:0]play_sample,output wire play_valid,input wire play_request);
 reg[23:0]capture[0:31],playback[0:31];reg[4:0]cp,pp;reg play_done;reg[31:0]initialized;
 wire loaded;pt_sync_bit ready(rf_tx_clk,rst_n,&initialized,loaded);
 wire cap_en,play_en;
 pt_sync_bit s0(rf_rx_clk,rst_n,capture_enable,cap_en);
 pt_sync_bit s1(rf_tx_clk,rst_n,playback_enable,play_en);
 assign capture_data=capture_done?capture[index]:24'b0;
 assign play_sample=playback[pp];assign play_valid=play_en&&loaded&&!play_done;
 always @(posedge spi_clk or negedge rst_n)
  if(!rst_n)initialized<=0;
  else if(memory_write)begin playback[index]<=memory_wdata;initialized[index]<=1;end
 always @(posedge rf_rx_clk or negedge rst_n)begin
  if(!rst_n)begin cp<=0;capture_done<=0;end
  else if(!cap_en)begin cp<=0;capture_done<=0;end
  else if(sample_valid&&!capture_done)begin capture[cp]<=sample;cp<=cp+1'b1;if(cp==31)capture_done<=1;end
 end
 always @(posedge rf_tx_clk or negedge rst_n)begin
  if(!rst_n)begin pp<=0;play_done<=0;end
  else if(!play_en)begin pp<=0;play_done<=0;end
  else if(play_request&&play_valid)begin pp<=pp+1'b1;if(pp==31)play_done<=1;end
 end
endmodule
