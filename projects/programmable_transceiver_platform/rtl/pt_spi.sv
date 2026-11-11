// Candidate Mode-0, MSB-first control ABI: command8/address8/data16.
// 0x80 writes; 0x00 reads. CS must delimit each 32-clock transaction.
module pt_spi(input wire rst_n,sclk,cs_n,mosi,output wire miso,output wire miso_oe,
 output wire wr_en,output wire[7:0]wr_addr,output wire[15:0]wr_data,
 output reg[7:0]rd_addr,input wire[15:0]rd_data,
 // Read candidates (timing closure 2026-11-11): rd_hi = address bits 7:1 (valid while count==15);
 // the register file returns the register value for {rd_hi,0} and {rd_hi,1}; both are registered on
 // the 16th rising edge (a full SCLK period after rd_hi settles) and address bit 0 selects on the
 // fall, so the read mux is no longer a half-period path (Mode 0 needs response bit 15 half a period
 // after the last address bit). The register values are thus sampled half an SCLK earlier (rising
 // instead of falling edge 16); register-file registers change only on SCLK falls, at write edges.
 output wire[6:0]rd_hi,input wire[15:0]rd_data0,rd_data1);
 // Timing (CLOSE_R2 sclk -8.4 ns at in-window ss): the write used to complete on the 32nd rising
 // edge with the last data bit taken straight from the MOSI pin, so pin -> write decode -> commit
 // enable fan-out (~750 active registers) had only the half period after the host's falling-edge
 // launch. The last bit is now registered like the others (shift[0] at the 32nd rising edge) and
 // the write is presented, from registers only, while count==32. pt_mgmt clocks pt_regfile and
 // pt_memory's SPI port on the inverted SCLK, so the write/commit lands on the falling edge that
 // follows the 32nd rising edge (always present in Mode 0: SCLK idles low before CS_N rises).
 // count stops at 33, so a host that sends extra clocks still produces exactly one write.
 // Timing (closure 2026-11-11): the command byte and the address are REGISTERS captured when they
 // complete (cmd_r after the 8th rising edge, rd_addr after the 16th) and held to the end of the
 // transaction, so the register-file write decode (case on wr_addr, command check) is stable for
 // 16 SCLK periods before the write edge (SDC multicycle from these registers into the register
 // file); only the data word and count==32 remain half-period paths. Same values as shift[31:24] /
 // shift[23:16] at count==32.
 reg[5:0]count;reg[31:0]shift;reg[15:0]read_value;reg miso_bit;reg[7:0]cmd_r;
 reg[15:0]cand0,cand1;
 assign rd_hi=shift[6:0];
 wire[15:0]rd_sel=rd_addr[0]?cand1:cand0;
 assign wr_en=!cs_n&&count==32&&cmd_r==8'h80;
 assign wr_addr=rd_addr;assign wr_data=shift[15:0];
 assign miso_oe=rst_n&&!cs_n;
 assign miso=cs_n?1'b0:miso_bit;
 wire serial_reset_n=rst_n&&!cs_n;
 always @(posedge sclk or negedge serial_reset_n)begin
  if(!serial_reset_n)begin count<=0;shift<=0;rd_addr<=0;cmd_r<=0;cand0<=0;cand1<=0;end
  else begin
   if(count<32)shift<={shift[30:0],mosi};
   if(count<33)count<=count+1'b1;
   if(count==7)cmd_r<={shift[6:0],mosi};
   if(count==15)begin rd_addr<={shift[6:0],mosi};cand0<=rd_data0;cand1<=rd_data1;end
  end
 end
 // Load after header at falling edge, ensuring first read bit is ready.
 always @(negedge sclk or negedge rst_n)begin
  if(!rst_n)begin read_value<=0;miso_bit<=0;end
  else if(!cs_n&&count==16)begin read_value<=rd_sel;miso_bit<=rd_sel[15];end
  else if(!cs_n&&count>16&&count<=31)miso_bit<=read_value[31-count];
  else miso_bit<=0;
 end
endmodule
