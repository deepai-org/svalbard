`timescale 1ns/1ps
// DG9-EG: lock-step equivalence of the pt_cdc_fifo read side (one read tree + two-entry skid) against the
// previous three-tree read side (sim/reference/pt_cdc_fifo_3tree.sv, module pt_cdc_fifo_ref, verbatim
// from commit cd456c5f). Both get identical inputs: jittered unrelated clocks (half periods drawn per
// edge, so near-coincident edges occur), random asynchronous resets in the middle of traffic, random
// pushes (ready-gated and ready-ignoring, so overflow), random pops (POPQ=1: gated by nonempty as the
// core does; POPQ=0: unconstrained, so underflow), and for MEMORY=2 playback phases (random play_last,
// loop / once, SPI writes on the SCLK fall while held in reset, then release and random pops).
// Checked on every read- and write-clock edge: every output port is identical (===), except dout, which
// must be identical whenever the reference reports data (!empty; for POPQ also nonempty). Exception: looped
// playback with play_last = 0, where the reference is wrong (see check) and dout is checked against entry 0.
// Negative controls (all fail, 2026-11-20): fetch without the write-pointer check, fetch one clock late
// (gate on wbin), fetch one clock early (gate on wgp, caught by the invariant check), drop the playback start
// fetch (pinit).
// Prints READSIDE_EQUIV_PASS.
module tb_rs_one #(parameter A=5,DEPTH=24,SPARE=3,MEMORY=0,POPQ=0,CNTPIPE=0,integer SEED=1,integer PHASES=40)
 (output reg done,output integer errors,output integer checks,output integer heads);
 localparam W=40;
 reg wclk=0,rclk=0,sclk=0,rst_n=0,push=0,pop_r=0,play=0,loop=0,swe=0;
 reg[W-1:0]din=0,sd=0;reg[A-1:0]plast=0,sidx=0,pidx=0;
 wire[W-1:0]d0,d1,k0,k1;wire f0,f1,e0,e1,n0,n1,r0,r1,o0,o1,u0,u1,wa0,wa1,ra0,ra1,t0,t1;
 wire[A:0]c0,c1,wp0,wp1,rp0,rp1,s0,s1;
 wire pop=POPQ?(pop_r&&n0):pop_r;
 pt_cdc_fifo_ref #(.W(W),.A(A),.DEPTH(DEPTH),.SPARE(SPARE),.MEMORY(MEMORY),.POPQ(POPQ),.CNTPIPE(CNTPIPE)) ref_(
  .wr_clk(wclk),.rd_clk(rclk),.rst_n(rst_n),.din(din),.push(push),.pop(pop),.dout(d0),.full(f0),.empty(e0),
  .nonempty(n0),.ready(r0),.rd_count(c0),.overflow(o0),.underflow(u0),.wr_active(wa0),.rd_active(ra0),
  .wr_ptr(wp0),.rd_ptr(rp0),.rd_ptr_step(s0),.rd_take(t0),.peek_idx(pidx),.peek(k0),.play(play),.play_loop(loop),
  .play_last(plast),.spi_clk(sclk),.spi_we(swe),.spi_idx(sidx),.spi_d(sd));
 pt_cdc_fifo #(.W(W),.A(A),.DEPTH(DEPTH),.SPARE(SPARE),.MEMORY(MEMORY),.POPQ(POPQ),.CNTPIPE(CNTPIPE)) dut(
  .wr_clk(wclk),.rd_clk(rclk),.rst_n(rst_n),.din(din),.push(push),.pop(pop),.dout(d1),.full(f1),.empty(e1),
  .nonempty(n1),.ready(r1),.rd_count(c1),.overflow(o1),.underflow(u1),.wr_active(wa1),.rd_active(ra1),
  .wr_ptr(wp1),.rd_ptr(rp1),.rd_ptr_step(s1),.rd_take(t1),.peek_idx(pidx),.peek(k1),.play(play),.play_loop(loop),
  .play_last(plast),.spi_clk(sclk),.spi_we(swe),.spi_idx(sidx),.spi_d(sd));
 integer seed=SEED,wlo=3,whi=9,rlo=3,rhi=9,pw=2,pr=2,gate=1,l0heads=0;
 always begin #(wlo+($urandom(seed)%(whi-wlo+1))+0.001*($urandom(seed)%1000)) wclk=~wclk; end
 always begin #(rlo+($urandom(seed)%(rhi-rlo+1))+0.001*($urandom(seed)%1000)) rclk=~rclk; end
 task check(input [79:0] where);
  begin
   checks=checks+1;
   if({f0,e0,n0,r0,c0,o0,u0,wa0,ra0,wp0,rp0,s0,t0}!=={f1,e1,n1,r1,c1,o1,u1,wa1,ra1,wp1,rp1,s1,t1}||k0!==k1)begin
    errors=errors+1;
    if(errors<10)$display("%0t %0s flags ref f%b e%b n%b r%b c%0d o%b u%b wp%0d rp%0d s%0d t%b | new f%b e%b n%b r%b c%0d o%b u%b wp%0d rp%0d s%0d t%b",
     $time,where,f0,e0,n0,r0,c0,o0,u0,wp0,rp0,s0,t0,f1,e1,n1,r1,c1,o1,u1,wp1,rp1,s1,t1);
   end
   // Looped playback of play_last = 0: the reference's roh1 reset value (entry 1) skips the playback wrap, so it
   // sends entries 0, 1, 2, .. DEPTH-1 and then entry 0 forever; the specified (and new) behaviour is entry 0 on
   // every clock. That case is checked against the stored entry 0 instead of the reference.
   if(MEMORY==2&&play&&loop&&plast==0&&(!e0||(POPQ&&n0)))begin
    heads=heads+1;l0heads=l0heads+1;
    if(d1!==ref_.mem[0])begin errors=errors+1;if(errors<10)$display("%m %0t %0s dout (loop, last 0) %h expected %h",$time,where,d1,ref_.mem[0]);end
   end else if(!e0||(POPQ&&n0))begin
    heads=heads+1;
    if(d0!==d1)begin errors=errors+1;if(errors<10)$display("%m %0t %0s dout ref %h new %h (rp %0d)",$time,where,d0,d1,rp0);end
   end
  end
 endtask
 // sample just after each edge has settled (outputs are registers or functions of registers / inputs)
 always @(posedge rclk)begin #0.2 check("rd");end
 // Internal invariants of the new read side (white box). Zero-delay simulation cannot see the CDC margin of a
 // fetch (the array and the published write pointer change on the same writer edge), so the margin is pinned
 // structurally: the fetch gate must equal "F's Gray code differs from wg2" (the two-flop-synchronized pointer),
 // and the skid queue must stay consistent (sk only behind dq, at most three entries, take only with a head).
 always @(posedge rclk)if(dut.rd_ready===1'b1)begin
  #0.1;
  if(dut.rdr!==(dut.fg!=dut.wg2)||dut.room!==!(dut.vq&&(dut.vs||dut.pv))||(dut.vs&&!dut.vq)||(dut.vs&&dut.pv))begin
   errors=errors+1;if(errors<10)$display("%m %0t read-side invariant: rdr %b fg %h wg2 %h room %b vq %b vs %b pv %b",
    $time,dut.rdr,dut.fg,dut.wg2,dut.room,dut.vq,dut.vs,dut.pv);
  end
 end
 always @(posedge rclk)if(dut.rd_ready===1'b1&&dut.take===1'b1&&dut.vq!==1'b1)begin
  errors=errors+1;if(errors<10)$display("%m %0t take without a head in the skid",$time);
 end
 always @(posedge wclk)begin #0.2 check("wr");end
 always @(posedge wclk)begin
  push<=($urandom(seed)%4<pw)&&(gate?r0:1'b1)&&!play;
  din<={$urandom(seed),8'($urandom(seed))};
 end
 always @(posedge rclk)begin
  pop_r<=$urandom(seed)%4<pr;
  pidx<=$urandom(seed)%DEPTH;
 end
 integer ph,i,len;
 initial begin
  errors=0;checks=0;heads=0;done=0;
  for(ph=0;ph<PHASES;ph=ph+1)begin
   rst_n=0;
   wlo=1+$urandom(seed)%6;whi=wlo+$urandom(seed)%8;rlo=1+$urandom(seed)%6;rhi=rlo+$urandom(seed)%8;
   pw=$urandom(seed)%5;pr=$urandom(seed)%5;gate=$urandom(seed)%4!=0;
   play=MEMORY==2&&($urandom(seed)%2);loop=$urandom(seed)%2;
   // half the phases use the wrap corners: 0, 1, 2, DEPTH-1, DEPTH (clamped), all ones (clamped)
   case($urandom(seed)%12)0:plast=0;1:plast=1;2:plast=2;3:plast=DEPTH-1;4:plast=DEPTH%(1<<A);5:plast={A{1'b1}};default:plast=$urandom(seed)%(1<<A);endcase
   #(20+$urandom(seed)%40);
   if(play)for(i=0;i<1+$urandom(seed)%(2*DEPTH);i=i+1)begin
    sidx=$urandom(seed)%DEPTH;sd={$urandom(seed),8'($urandom(seed))};swe=$urandom(seed)%5!=0;
    #3 sclk=1;#3 sclk=0;#3 swe=0;
   end
   #($urandom(seed)%30) rst_n=1;
   len=200+$urandom(seed)%3000;
   #(len);
  end
  rst_n=0;#50;
  if(l0heads)$display("%m: %0d heads in looped play_last=0 checked against entry 0",l0heads);
  done=1;
 end
endmodule
module tb_cdc_fifo_readside_equiv;
 wire[6:0]dn;integer e[0:6],c[0:6],h[0:6];
 tb_rs_one #(.A(5),.DEPTH(28),.MEMORY(1),.SEED(11),.PHASES(60)) ingress(dn[0],e[0],c[0],h[0]);
 tb_rs_one #(.A(5),.DEPTH(24),.SPARE(4),.MEMORY(2),.POPQ(1),.CNTPIPE(1),.SEED(22),.PHASES(80)) egress(dn[1],e[1],c[1],h[1]);
 tb_rs_one #(.A(5),.DEPTH(24),.SPARE(4),.MEMORY(2),.POPQ(1),.CNTPIPE(1),.SEED(33),.PHASES(80)) egress2(dn[2],e[2],c[2],h[2]);
 tb_rs_one #(.A(4),.DEPTH(16),.MEMORY(2),.POPQ(0),.SEED(44),.PHASES(60)) pow2(dn[3],e[3],c[3],h[3]);
 tb_rs_one #(.A(3),.DEPTH(6),.SPARE(2),.MEMORY(2),.POPQ(1),.SEED(55),.PHASES(80)) small6(dn[4],e[4],c[4],h[4]);
 tb_rs_one #(.A(3),.DEPTH(4),.SPARE(1),.MEMORY(2),.POPQ(0),.SEED(66),.PHASES(80)) small4(dn[5],e[5],c[5],h[5]);
 tb_rs_one #(.A(5),.DEPTH(28),.MEMORY(0),.POPQ(1),.SEED(77),.PHASES(60)) popq28(dn[6],e[6],c[6],h[6]);
 integer k,tot,tc,th,few;
 initial begin
  wait(&dn);tot=0;tc=0;th=0;few=0;
  for(k=0;k<7;k=k+1)begin $display("config %0d: checks %0d heads compared %0d errors %0d",k,c[k],h[k],e[k]);tot=tot+e[k];tc=tc+c[k];th=th+h[k];if(h[k]<5000)few=few+1;end
  if(tot==0&&few==0)$display("READSIDE_EQUIV_PASS checks=%0d heads=%0d",tc,th);else $display("READSIDE_EQUIV_FAIL errors=%0d configs with < 5000 heads compared %0d",tot,few);
  $finish;
 end
endmodule
