// Candidate Mode-0, MSB-first control ABI: command8/address8/data16.
// 0x80 writes; 0x00 reads. CS must delimit each 32-clock transaction.
module pt_spi(input wire rst_n,sclk,cs_n,mosi,output wire miso,output wire miso_oe,
 output wire wr_en,output wire[7:0]wr_addr,output wire[15:0]wr_data,
 output reg[7:0]rd_addr,input wire[15:0]rd_data);
 reg[5:0]count;reg[30:0]shift;reg[15:0]read_value;reg miso_bit;
 assign wr_en=!cs_n&&count==31&&shift[30:23]==8'h80;
 assign wr_addr=shift[22:15];assign wr_data={shift[14:0],mosi};
 assign miso_oe=!cs_n;
 assign miso=cs_n?1'b0:miso_bit;
 wire serial_reset_n=rst_n&&!cs_n;
 always @(posedge sclk or negedge serial_reset_n)begin
  if(!serial_reset_n)begin count<=0;shift<=0;rd_addr<=0;end
  else begin
   if(count<32)begin shift<={shift[29:0],mosi};count<=count+1'b1;end
   if(count==15)rd_addr<={shift[6:0],mosi};
  end
 end
 // Load after header at falling edge, ensuring first read bit is ready.
 always @(negedge sclk or negedge rst_n)begin
  if(!rst_n)begin read_value<=0;miso_bit<=0;end
  else if(!cs_n&&count==16)begin read_value<=rd_data;miso_bit<=rd_data[15];end
  else if(!cs_n&&count>16&&count<=31)miso_bit<=read_value[31-count];
  else miso_bit<=0;
 end
endmodule

module pt_control(input wire rst_n,sclk,cs_n,mosi,output wire miso,miso_oe,
 input wire[15:0]status,output reg enable,mode8,
 output reg[15:0]rf_trim,wire_trim,clock_trim,
 output wire memory_write,output wire[4:0]memory_index,output wire[23:0]memory_wdata,
 input wire[23:0]capture_data,input wire capture_done,
 output reg playback_enable,capture_enable);
 wire wr_en;wire[7:0]wa,ra;wire[15:0]wd;reg[15:0]rd;
 reg[4:0]index;reg[11:0]play_i;reg rejected;reg[15:0]s1,s2;reg c1,c2;
 pt_spi spi(rst_n,sclk,cs_n,mosi,miso,miso_oe,wr_en,wa,wd,ra,rd);
 assign memory_index=index;assign memory_wdata={wd[11:0],play_i};
 assign memory_write=wr_en&&wa==8'h22&&!enable;
 always @*begin
  case(ra)
   0:rd=16'h5356;1:rd={15'b0,enable};2:rd={15'b0,mode8};3:rd=s2;
   4:rd={15'b0,rejected};8:rd=16'h0001;
   8'h10:rd=rf_trim;8'h11:rd=wire_trim;8'h12:rd=clock_trim;
   8'h20:rd={11'b0,index};8'h23:rd={14'b0,capture_enable,playback_enable};
   8'h24:rd={15'b0,c2};8'h25:rd=capture_data[15:0];8'h26:rd={8'b0,capture_data[23:16]};
   default:rd=16'h0;
  endcase
 end
 always @(posedge sclk or negedge rst_n)begin
  if(!rst_n)begin enable<=0;mode8<=0;rf_trim<=0;wire_trim<=0;clock_trim<=0;index<=0;play_i<=0;
   rejected<=0;s1<=0;s2<=0;c1<=0;c2<=0;playback_enable<=0;capture_enable<=0;end
  else begin
   s1<=status;s2<=s1;c1<=capture_done;c2<=c1;
   if(wr_en)begin
    if(wa==1)enable<=wd[0];
    else if(wa==8'h20)index<=wd[4:0];
    else if(enable)rejected<=1;
    else case(wa)
     2:mode8<=wd[0];4:rejected<=0;8'h10:rf_trim<=wd;8'h11:wire_trim<=wd;8'h12:clock_trim<=wd;
     8'h21:play_i<=wd[11:0];8'h22:begin end
     8'h23:begin playback_enable<=wd[0];capture_enable<=wd[1];end
     default:rejected<=1;
    endcase
   end
  end
 end
endmodule
