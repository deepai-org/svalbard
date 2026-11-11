// Frozen copy of the pre-2026-11-10 rtl/pt_spi.sv (write completes on the 32nd rising edge, last bit
// taken from MOSI) used only by sim/reference/pt_control.sv as the SPI ABI reference.
// Candidate Mode-0, MSB-first control ABI: command8/address8/data16.
// 0x80 writes; 0x00 reads. CS must delimit each 32-clock transaction.
module pt_spi_legacy(input wire rst_n,sclk,cs_n,mosi,output wire miso,output wire miso_oe,
 output wire wr_en,output wire[7:0]wr_addr,output wire[15:0]wr_data,
 output reg[7:0]rd_addr,input wire[15:0]rd_data);
 reg[5:0]count;reg[30:0]shift;reg[15:0]read_value;reg miso_bit;
 assign wr_en=!cs_n&&count==31&&shift[30:23]==8'h80;
 assign wr_addr=shift[22:15];assign wr_data={shift[14:0],mosi};
 assign miso_oe=rst_n&&!cs_n;
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
