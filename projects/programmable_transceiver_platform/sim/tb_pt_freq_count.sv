// Self-checking test of rtl/pt_freq_count.sv (P3-7): source select, exact lock, target ratio,
// offset vs tolerance, raw count, lost lock when the source stops (sticky), source change handled as
// restart, disable clears, SCLK stopped freezes the published value, diff saturation. Prints FREQ_COUNT_PASS.
`timescale 1ns/1ps
module tb_pt_freq_count;
 reg rst_n=1,ref_clk=0,sclk=0,run1=1,sclk_run=1;
 reg[2:0]src_sel=0,tol=2;reg[1:0]win=0,cnt=1;reg[15:0]target=256;
 real t0=50.0,t3=12.5;reg[5:0]s=0;
 always #25 ref_clk=~ref_clk;                       // 20 MHz reference
 always #(t0/2) if(run1) s[0]=~s[0];                // tx_ring_fbck
 always #(t3/2) s[3]=~s[3];                         // vco_replica (80 MHz)
 always #7 s[5]=~s[5];                              // lc_prescale (~71.4 MHz)
 always #50 if(sclk_run) sclk=~sclk;
 wire lref,locked,lost;wire[13:0]diff;wire[15:0]count;
 // Register-file commit model: every configuration change is one commit (commit_toggle flips once
 // per change event, in the same time step as the bus change).
 reg ct=0,ct_pend=0;
 always @(src_sel,tol,win,cnt,target) if(!ct_pend)begin ct_pend=1;#0.001 ct=~ct;ct_pend=0;end
 pt_freq_count dut(.rst_n(rst_n),.cfg_source(src_sel),.cfg_window(win),.cfg_tol(tol),.cfg_count(cnt),.cfg_target(target),
  .src(s),.ref_clk(ref_clk),.sclk(sclk),.locked_ref(lref),.locked(locked),.lost_lock(lost),.diff(diff),.count(count),
  .commit_toggle(ct));
 // eval_window: the multicycle evaluation's sources (snapshot, fb_prev, captured configuration unless
 // the window is marked fresh) hold from the snapshot edge to the result-load edge 5 cycles later.
 reg[63:0]hist[0:5];integer hk,ev_viol=0,ev_seen=0;
 wire[63:0]evsrc={dut.snap_h,dut.snap_l,dut.fb_prev,dut.cfg_src_r,dut.cfg_r};
 // good / r_locked (timing closure 2026-11-11: also multicycle sources of their own update) hold too
 reg[4:0]ghist[0:5];wire[4:0]gsrc={dut.good,dut.r_locked};
 always @(posedge ref_clk)begin
  if(dut.run&&dut.ev_go)begin
   ev_seen=ev_seen+1;
   for(hk=0;hk<4;hk=hk+1)if(hist[hk][63:26]!==evsrc[63:26]||(!dut.cfg_fresh&&hist[hk][25:0]!==evsrc[25:0])||ghist[hk]!==gsrc)ev_viol=ev_viol+1;
  end
  for(hk=5;hk>0;hk=hk-1)begin hist[hk]=hist[hk-1];ghist[hk]=ghist[hk-1];end hist[0]=evsrc;ghist[0]=gsrc;
 end
 integer errs=0;
 task check(input l,input lo,input integer dlo,input integer dhi,input integer clo,input integer chi,input[8*40-1:0]what);
  integer d; begin d=$signed(diff);
   if(locked!==l||lost!==lo||d<dlo||d>dhi||count<clo||count>chi)begin errs=errs+1;$display("FAIL %0s: locked=%b lost=%b diff=%0d count=%0d",what,locked,lost,d,count);end
   else $display("ok   %0s: locked=%b lost=%b diff=%0d count=%0d",what,locked,lost,d,count);
  end endtask
 initial begin
  #1 rst_n=0; #200 rst_n=1; #200;
  src_sel=1; #(256*50*5); check(1,0,0,0,256,256,"src1 exact");
  src_sel=0; #3000; check(0,0,0,0,0,0,"off clears");
  target=1024; src_sel=4; #(256*50*5); check(1,0,0,0,1024,1024,"src4 4x ref");
  src_sel=0; #3000; target=256; tol=0; t0=50.0/1.01; src_sel=1; #(256*50*6); check(0,0,2,3,258,259,"+1% tol0 no lock");
  src_sel=0; #3000; tol=3; src_sel=1; #(256*50*6); check(1,0,2,3,258,259,"+1% tol4 lock");
  run1=0; #(256*50*4); check(0,1,-256,-256,0,0,"src stopped: lost");
  run1=1; #(256*50*6); check(1,1,2,3,258,259,"src back: lost sticky");
  sclk_run=0; run1=0; #(256*50*4); check(1,1,2,3,258,259,"sclk stopped: frozen");
  sclk_run=1; #2000; check(0,1,-256,-256,0,0,"sclk resumed");
  run1=1; src_sel=6; target=914; tol=5; #(256*50*6); check(1,0,-16,16,898,930,"switch to src6 restarts");
  src_sel=0; #3000; win=3; target=0; tol=0; cnt=0; src_sel=4; #(4096*50*3); check(0,0,8191,8191,16384,16384,"saturated diff high");
  if(ev_viol!=0||ev_seen<20)begin errs=errs+1;$display("FAIL eval_window: %0d violations in %0d evaluations",ev_viol,ev_seen);end
  else $display("ok   eval_window: %0d evaluations, sources stable 5 cycles",ev_seen);
  if(errs==0)$display("FREQ_COUNT_PASS");else $display("FREQ_COUNT_FAIL %0d",errs);
  $finish;
 end
endmodule
