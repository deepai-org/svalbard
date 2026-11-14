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
 // the write is presented, from registers only, after the 32nd rising edge. pt_mgmt clocks pt_regfile
 // and pt_memory's SPI port on the inverted SCLK, so the write/commit lands on the falling edge that
 // follows the 32nd rising edge (always present in Mode 0: SCLK idles low before CS_N rises).
 // count stops at 33, so a host that sends extra clocks still produces exactly one write.
 // Timing (closure 2026-11-11): the command byte and the address are REGISTERS captured when they
 // complete (cmd_r after the 8th rising edge, rd_addr after the 16th) and held to the end of the
 // transaction, so the register-file write decode (case on wr_addr, command check) is stable for
 // 16 SCLK periods before the write edge (SDC multicycle from these registers into the register
 // file); only the data word and the write qualifier remain half-period paths. Same values as
 // shift[31:24] / shift[23:16] at count==32.
 // CS_N vs the write edge (DT-11 structural fix, 2026-11-13). The write qualifier used to be
 // `!cs_n && count==32 && cmd_r==8'h80`: combinational from the CS_N pin and from a counter that CS_N
 // resets asynchronously, so a CS_N rise near the committing SCLK fall reached the ~750 register-file
 // enables as an untimed runt (partial write). Now:
 //  - wr_en is ONE flop (wr_q), set on the 32nd rising edge (count==31 and the command register is
 //    0x80), cleared on the next SCLK rising edge whenever that comes (33rd clock of the same
 //    transaction, first clock of the next one, or a clock for another device with CS_N high: count
 //    is then 0). Reset by rst_n only.
 //  - wr_addr (rd_addr), wr_data (shift) and cmd_r are reset by rst_n only, NOT by CS_N; they change
 //    only on SCLK rising edges. Each is rewritten in every transaction before it is used (cmd_r at
 //    clock 8, rd_addr/cand at clock 16, shift every clock), so stale values are never consumed.
 //  - only `count` keeps the asynchronous CS_N reset (serial_reset_n): it must restart without a clock.
 // Nothing in the cone of wr_en/wr_addr/wr_data can therefore change between the 32nd rising edge
 // and the next rising edge: the falling edge in between (exactly one, Mode 0) commits a complete
 // write whatever CS_N does, and a transaction that never reaches its 32nd rising edge writes
 // nothing. Remaining host rule = ordinary Mode-0 framing against RISING edges only: CS_N stable from
 // the count recovery time before to the removal time after each SCLK rising edge it frames (CS_N
 // falls >= tCSS before the first rise, rises >= tCSH after the 32nd rise; both are flop
 // recovery/removal checks of `count` against sclk-rise, timed by STA through the CS_N input delay).
 // CS_N has no timing relation to the committing falling edge any more.
 // A CS_N rise that violates tCSH at the 32nd rising edge (count being cleared while it is sampled):
 // every transient value of count on the way 31 -> 0 is < 32, so the last data bit is still shifted
 // in; the address register is guarded by hdr_done (a flop, set from the 16th edge of a transaction,
 // cleared at the first edge of the next), so a transient count==15 cannot rewrite the address in
 // the same edge that sets wr_q; cmd_r may be rewritten but is not used after wr_q is captured. The
 // only exposed element is wr_q itself (one flop, D changing at its clock edge), which has half an
 // SCLK period to resolve before the commit: the write is still complete (right address and data)
 // or absent. A CS_N FALL closer than the recovery time to the first rising edge (tCSS) is not
 // protected: the bit counter may miscount.
 reg[5:0]count;reg[31:0]shift;reg[15:0]read_value;reg miso_bit;reg[7:0]cmd_r;
 reg[15:0]cand0,cand1;reg wr_q,hdr_done;
 assign rd_hi=shift[6:0];
 wire[15:0]rd_sel=rd_addr[0]?cand1:cand0;
 assign wr_en=wr_q;
 assign wr_addr=rd_addr;assign wr_data=shift[15:0];
 assign miso_oe=rst_n&&!cs_n;
 assign miso=cs_n?1'b0:miso_bit;
 wire serial_reset_n=rst_n&&!cs_n;
 // The only state CS_N resets (asynchronously).
 always @(posedge sclk or negedge serial_reset_n)begin
  if(!serial_reset_n)count<=0;
  else if(count<33)count<=count+1'b1;
 end
 // Datapath and write qualifier: SCLK rising edge, reset by rst_n only (see the note above).
 always @(posedge sclk or negedge rst_n)begin
  if(!rst_n)begin shift<=0;rd_addr<=0;cmd_r<=0;cand0<=0;cand1<=0;wr_q<=1'b0;hdr_done<=1'b0;end
  else begin
   if(count<32)shift<={shift[30:0],mosi};
   if(count==7)cmd_r<={shift[6:0],mosi};
   if(count==15&&!hdr_done)begin rd_addr<={shift[6:0],mosi};cand0<=rd_data0;cand1<=rd_data1;end
   hdr_done<=count>=15;
   wr_q<=count==31&&cmd_r==8'h80;
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
