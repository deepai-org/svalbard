// CS_N rise vs the SPI write edge (DT-11 structural fix in rtl/pt_spi.sv).
// Run by verification/check_spi_csn_race.py on the RTL (zero-delay pt_spi) and on a yosys gate
// netlist of pt_spi with the spread transport-delay cells of sim/spi_race_cells.sv (+define+GL).
//
// Consumer model = what pt_mgmt does with pt_spi's outputs: four 16-bit registers (addresses
// 0x10..0x13) and a commit counter, all clocked on the SCLK FALLING edge. Every register bit sees
// wr_en / the address decode / its data bit through its own transport delay (0..2.5 ns: the enable
// fan-out to ~750 flops), and a bit whose enable or data changes within +-TW of the falling edge
// becomes X (a runt enable is a metastable or partial commit, never "fine").
//
// Property checked after EVERY transaction: the addressed register is entirely the new word or
// entirely the old word (old = ~new, so any mixture shows), no bit is X, no other register changed,
// and the commit counter moved by exactly 1 (written) or 0 (not written), consistently.
// Sweeps of the CS_N rising edge:
//  F  across the committing SCLK fall (the DT-11 race): -95 ns .. +95 ns in 1 ns steps and
//     -20 ns .. +20 ns in 10 ps steps. Required: the write ALWAYS happens (the 32nd rising edge was
//     seen with CS_N low), completely.
//  R  across the 32nd SCLK RISING edge (host violates tCSH), -5 ns .. +5 ns in 10 ps steps.
//     Required: complete write or no write, right address. Outside +-RW of the edge the outcome
//     must also be the deterministic one (no write before, write after).
//  X  extra / missing clocks, clocks with CS_N high (shared bus), reads: exactly one write per
//     32-clock write transaction, none otherwise; the read path returns the register.
//  L  (review S4) long frames: 40 clocks with a trailing 0xFF (the rescue-mode framing of
//     rtl/pt_por_path.sv), 100 / 132 / 200 clocks whose bits after the 32nd repeat a complete write
//     command to ANOTHER register (a bit counter that wraps instead of saturating writes it):
//     exactly one write, to the first address.
//  C  (review S4) commands 0x81, 0xC0, 0xFF, 0x01, 0x7F, 0x40 with 32 clocks: no write.
//  S1 KNOWN LIMIT (review S1; pt_spi.sv is NOT changed for it): wr_q stays set from the 32nd rising
//     edge to the NEXT SCLK rising edge. An SCLK runt in idle that the falling-edge register file
//     sees but the rising-edge flops of pt_spi do not is a second commit edge with wr_en still 1:
//     the frame is committed twice. Harmless for a plain register write (same word), not for a
//     frame that is not idempotent (commit counter here; a COMMIT frame in the register file).
//     The bench drives such a runt on the consumer's clock only (csclk) and RECORDS the outcome
//     (line "KNOWN LIMIT S1 ..."); it then asserts the host-side mitigation: a 33rd clock in the
//     frame clears wr_q, after which the same runt commits nothing. Board rule: SCLK glitch-free
//     between transactions (Schmitt pad input on SCLK); host rule if in doubt: 33 or more clocks.
`timescale 1ps/1ps
module tb_spi_csn_race;
 integer seed=1,meta_events=0;
 localparam integer HALF=100000;   // 5 MHz
 localparam integer TW=150;        // consumer setup/hold window
 localparam integer RW=2000;       // keep-out reported around the 32nd rising edge (GL only)
 reg rst_n=1,sclk=0,cs_n=1,mosi=0;
 reg runt_c=0;              // S1: an SCLK pulse that only the falling-edge consumer sees
 wire csclk=sclk|runt_c;    // the consumer's (register file's) view of SCLK
 reg[31:0]tailw=32'h0;      // MOSI bits after the 32nd clock (repeated every 32 clocks)
 wire miso,miso_oe,wr_en;wire[7:0]wr_addr,rd_addr;wire[15:0]wr_data;wire[6:0]rd_hi;
 reg[15:0]r[0:3];integer ncommit=0;
 wire hit=rd_hi[6:1]==6'b000100; // addresses 0x10..0x13
 wire[15:0]rd_data0=hit ? r[{rd_hi[0],1'b0}] : 16'h0;
 wire[15:0]rd_data1=hit ? r[{rd_hi[0],1'b1}] : 16'h0;
 pt_spi dut(.rst_n(rst_n),.sclk(sclk),.cs_n(cs_n),.mosi(mosi),.miso(miso),.miso_oe(miso_oe),
  .wr_en(wr_en),.wr_addr(wr_addr),.wr_data(wr_data),.rd_addr(rd_addr),.rd_data(16'h0),
  .rd_hi(rd_hi),.rd_data0(rd_data0),.rd_data1(rd_data1));

 // ---- consumer: per-bit skewed copies of the write bus, falling-edge capture, X on violation
 time t_fall=0;
 always @(negedge csclk) t_fall=$time;
 genvar gi,gb;
 generate for(gi=0;gi<4;gi=gi+1)begin: regs
  for(gb=0;gb<16;gb=gb+1)begin: bits
   integer de,dd;reg en_d,d_d;time t_en,t_d;
   initial begin de=0;dd=0;en_d=0;d_d=0;t_en=0;t_d=0;
    #1 de={$random(seed)}%2500;dd={$random(seed)}%2500;end
   wire sel=wr_en&&wr_addr==8'h10+gi;
   always @(sel) en_d<= #(de) sel;
   always @(wr_data[gb]) d_d<= #(dd) wr_data[gb];
   always @(en_d)begin t_en=$time;if($time-t_fall<TW&&$time>TW&&rst_n)r[gi][gb]<=1'bx;end
   always @(d_d)begin t_d=$time;if($time-t_fall<TW&&$time>TW&&rst_n&&en_d)r[gi][gb]<=1'bx;end
   always @(negedge csclk or negedge rst_n)
    if(!rst_n)r[gi][gb]<=1'b0;
    else if($time-t_en<TW||(en_d!==1'b0&&$time-t_d<TW))r[gi][gb]<=1'bx;
    else if(en_d)r[gi][gb]<=d_d;
  end
 end endgenerate
 // commit counter: its own skewed enable; an enable edge in its window counts as a failure
 integer dc=0;reg en_c=0;time t_enc=0;integer c_viol=0;
 initial #1 dc={$random(seed)}%2500;
 always @(wr_en) en_c<= #(dc) wr_en;
 always @(en_c)begin t_enc=$time;if($time-t_fall<TW&&$time>TW&&rst_n)c_viol=c_viol+1;end
 always @(negedge csclk)if(rst_n)begin
  if($time-t_enc<TW)c_viol=c_viol+1;else if(en_c)ncommit=ncommit+1;
 end

 // ---- host
 integer fails=0,checks=0;
 task fail(input [1023:0] msg);begin
  fails=fails+1;$display("FAIL %0s (t=%0t)",msg,$time);
  if(fails>=20)begin $display("SPI_CSN_RACE_FAIL %0d failing checks of %0d (stopped early)",fails,checks);$finish;end
 end endtask
 // One transaction of nclk clocks. cs_rise: time of the CS_N rise relative to the falling edge that
 // follows the 32nd rising edge (ps; may be negative). The SCLK waveform is never altered by CS_N.
 reg[15:0]rdata;
 task txn(input[7:0]cmd,addr,input[15:0]data,input integer nclk,input integer cs_rise);
  reg[31:0]w;integer k,dly;
  begin
   w={cmd,addr,data};rdata=0;
   cs_n=0;dly=64*HALF+cs_rise; // rising edge k (1..32) at (2k-1)*HALF, falling edge 32 at 64*HALF
   fork
    begin #(dly);cs_n=1;end
    begin
     for(k=0;k<nclk;k=k+1)begin
      mosi=k<32?w[31-k]:tailw[31-(k%32)];
      #(HALF) sclk=1;if(k>=16&&k<32)rdata[31-k]=miso;
      #(HALF) sclk=0;
     end
    end
   join
   #(2*HALF);
  end
 endtask
 // CS_N high, n clocks for "another device"
 task foreign(input integer n);integer k;begin
  for(k=0;k<n;k=k+1)begin mosi=$random(seed);#(HALF) sclk=1;#(HALF) sclk=0;end #(HALF);
 end endtask
 function integer late(input integer nclk);late=(nclk>32?(nclk-32)*2*HALF:0)+HALF/2;endfunction

 integer idx=0;reg[15:0]pat;reg[15:0]snap[0:3];integer c0;
 // mode 1: must write; 0: must not write; 2: either (but all or nothing)
 task attempt(input integer nclk,input integer cs_rise,input integer mode,input [255:0]tag);
  integer j,wrote;reg[7:0]a;
  begin
   idx=idx+1;a=8'h10+(idx%4);pat=$random(seed);
   txn(8'h80,a,~pat,32,HALF/2);                // clean preload of the complement
   if(r[idx%4]!==~pat)fail("preload write did not land");
   for(j=0;j<4;j=j+1)snap[j]=r[j];c0=ncommit;
   txn(8'h80,a,pat,nclk,cs_rise);
   checks=checks+1;wrote=-1;
   if(r[idx%4]===pat)wrote=1;else if(r[idx%4]===~pat)wrote=0;
   if(wrote<0)begin $display("  %0s cs_rise=%0d ps: reg=%h old=%h new=%h",tag,cs_rise,r[idx%4],~pat,pat);fail("register corrupted (partial or X)");end
   for(j=0;j<4;j=j+1)if(j!=idx%4&&r[j]!==snap[j])begin $display("  %0s cs_rise=%0d ps: r[%0d]=%h was %h",tag,cs_rise,j,r[j],snap[j]);fail("another register changed");end
   if(wrote>=0&&ncommit-c0!=wrote)begin $display("  %0s cs_rise=%0d ps: commits=%0d wrote=%0d",tag,cs_rise,ncommit-c0,wrote);fail("commit count inconsistent");end
   if(c_viol!=0)begin $display("  %0s cs_rise=%0d ps",tag,cs_rise);fail("wr_en edge inside the commit window");c_viol=0;end
   if(mode==1&&wrote==0)begin $display("  %0s cs_rise=%0d ps",tag,cs_rise);fail("write lost");end
   if(mode==0&&wrote==1)begin $display("  %0s cs_rise=%0d ps",tag,cs_rise);fail("write without 32 clocks");end
  end
 endtask

 // 32 clocks with a command other than 0x80 / 0x00: must not write
 task attempt_cmd(input[7:0]cmd);
  integer j;reg[7:0]a;
  begin
   idx=idx+1;a=8'h10+(idx%4);pat=$random(seed);
   txn(8'h80,a,~pat,32,HALF/2);
   if(r[idx%4]!==~pat)fail("preload write did not land");
   for(j=0;j<4;j=j+1)snap[j]=r[j];c0=ncommit;
   txn(cmd,a,pat,32,HALF/2);
   checks=checks+1;
   for(j=0;j<4;j=j+1)if(r[j]!==snap[j])begin $display("  command %h: r[%0d]=%h was %h",cmd,j,r[j],snap[j]);fail("a command other than 0x80 wrote a register");end
   if(ncommit!=c0)begin $display("  command %h: commits=%0d",cmd,ncommit-c0);fail("a command other than 0x80 committed");end
   if(c_viol!=0)begin fail("wr_en edge inside the commit window");c_viol=0;end
  end
 endtask
 // long frame: the bits after the 32nd are a write of 16'hBEEF to the NEXT register, repeated
 task attempt_long(input integer nclk,input [255:0]tag);
  reg[7:0]other;
  begin
   other=8'h10+((idx+2)%4);tailw={8'h80,other,16'hBEEF};
   attempt(nclk,late(nclk),1,tag);
   tailw=32'h0;
  end
 endtask
 // S1: 300 ps SCLK runt in idle, on the consumer's clock only
 task runt_in_idle;begin #(3*HALF) runt_c=1;#300 runt_c=0;#(3*HALF);end endtask

 integer off,n_w=0,n_nw=0,lo_w,hi_nw,m0,s1_extra;
 initial begin
  if($value$plusargs("seed=%d",seed))begin end
  // give the simulator the edges that level-sensitive resets do not need in silicon
  cs_n=0;#1000 rst_n=0;#(HALF) cs_n=1;#(4*HALF) rst_n=1;#(4*HALF);
  c_viol=0; // csclk is a net: its X -> 0 at time 0 is a "falling edge" for the consumer model (before the reset above)
  // F: across the committing falling edge
  for(off=-95000;off<=95000;off=off+1000)attempt(32,off,1,"F-coarse");
  for(off=-20000;off<=20000;off=off+10)attempt(32,off,1,"F-fine");
  if(meta_events!=0)fail("a pt_spi flop saw a setup/hold violation during the falling-edge sweep");
  $display("F sweep: %0d points, fails so far %0d, flop setup/hold events %0d",checks,fails,meta_events);
  // R: across the 32nd rising edge (falling edge is HALF later; rising edge at cs_rise = -HALF)
  lo_w=1000000;hi_nw=-1000000;m0=meta_events;
  for(off=-5000;off<=5000;off=off+10)begin
   attempt(32,-HALF+off,(off<-RW)?0:(off>RW)?1:2,"R");
   if(r[idx%4]===pat)begin n_w=n_w+1;if(off<lo_w)lo_w=off;end
   else begin n_nw=n_nw+1;if(off>hi_nw)hi_nw=off;end
  end
  $display("R sweep: %0d written, %0d not written; latest no-write at %0d ps, earliest write at %0d ps after the 32nd rising edge; flop setup/hold events %0d",
   n_w,n_nw,hi_nw,lo_w,meta_events-m0);
  // X: clock counts and bystanders
  attempt(31,HALF/2-2*HALF,0,"31 clocks");
  attempt(16,-30*HALF,0,"16 clocks");
  attempt(33,late(33),1,"33 clocks");
  attempt(34,late(34),1,"34 clocks");
  attempt(40,late(40),1,"40 clocks");
  attempt(32,HALF/2,1,"then foreign clocks");c0=ncommit;foreign(70);
  if(ncommit!=c0)fail("commit while CS_N high (foreign clocks)");
  attempt(32,-HALF/2,1,"CS_N rises while SCLK high");c0=ncommit;foreign(3);
  if(ncommit!=c0)fail("second commit after CS_N rose with SCLK high");
  // write, read back through MISO, read is not a write
  txn(8'h80,8'h12,16'hC35A,32,HALF/2);c0=ncommit;
  txn(8'h00,8'h12,16'hFFFF,32,HALF/2);checks=checks+1;
  if(rdata!==16'hC35A)begin $display("  read %h",rdata);fail("read-back mismatch");end
  txn(8'h00,8'h13,16'h8000,32,HALF/2);checks=checks+1;
  if(rdata!==r[3])fail("read-back mismatch (odd address)");
  if(ncommit!=c0)fail("read committed a write");
  if(r[2]!==16'hC35A)fail("read changed the register");
  // L: long frames (review S4)
  tailw=32'hFFFFFFFF;attempt(40,late(40),1,"40 clocks, trailing FF");tailw=32'h0;
  attempt_long(64,"64 clocks, second write command in the tail");
  attempt_long(100,"100 clocks, write commands in the tail");
  attempt_long(132,"132 clocks, write commands in the tail");
  attempt_long(200,"200 clocks, write commands in the tail");
  // C: commands that must not write (review S4)
  attempt_cmd(8'h81);attempt_cmd(8'hC0);attempt_cmd(8'hFF);attempt_cmd(8'h01);attempt_cmd(8'h7F);attempt_cmd(8'h40);
  // S1 KNOWN LIMIT: recorded, not required (see the header)
  attempt(32,HALF/2,1,"S1 frame");c0=ncommit;runt_in_idle;s1_extra=ncommit-c0;checks=checks+1;
  if(r[idx%4]!==pat)fail("S1 runt corrupted the register (only a repeated commit of the same word is the known limit)");
  $display("KNOWN LIMIT S1 (not fixed): SCLK runt in idle seen by the falling-edge side only, after a 32-clock write frame: %0d extra commit(s), register %0s",
   s1_extra,r[idx%4]===pat?"unchanged (same word rewritten)":"CORRUPTED");
  foreign(1); // an SCLK rising edge clears wr_q
  attempt(33,late(33),1,"S1 mitigation frame (33 clocks)");c0=ncommit;runt_in_idle;checks=checks+1;
  if(ncommit!=c0||r[idx%4]!==pat)fail("S1 mitigation: runt after a 33-clock frame committed");
  $display("S1 mitigation: the same runt after a 33-clock frame: %0d extra commit(s)",ncommit-c0);
  if(fails==0)$display("SPI_CSN_RACE_PASS %0d checks",checks);
  else $display("SPI_CSN_RACE_FAIL %0d failing checks of %0d",fails,checks);
  $finish;
 end
endmodule
