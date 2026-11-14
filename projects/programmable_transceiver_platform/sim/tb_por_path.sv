// rtl/pt_por_path.sv: reset path with the strap (first) and the pad-free keyed (second) POR override.
// Run by verification/check_por_path.py: on the RTL and on a copy with a delayed ovr clock pin (both
// must pass); on mutated copies (each must FAIL in at least one of the two forms).
// The 17 storage elements (dut.key[15:0], dut.ovr) are started in several states (0, all 1, X, KEY,
// ~KEY) in every power-up scenario, and in ALL 2^17 states in the static enumeration S10.
// Monitors that run all the time:
//  I1  RESET_N low => rst_n low.
//  I2  por_n high  => rst_n == RESET_N (the override logic is invisible on a healthy, released POR).
//  I3  ovr_armed rises only at a RESET_N rising edge that finds SCLK high.
//  I4  rst_n never shows a zero-width or runt pulse: every rst_n edge is counted and each scenario
//      states how many rising and falling edges it expects.
`timescale 1ns/1ps
module tb_por_path;
 localparam [15:0] KEY=16'hC3A5; // deliberately not taken from the DUT
 reg reset_n_pad=1,por_n=0,por_bypass=0,cs_n=1,sclk=0,mosi=0;
 wire rst_n,ovr_armed,por_masked;
 pt_por_path dut(.reset_n_pad(reset_n_pad),.por_n(por_n),.por_bypass(por_bypass),
  .spi_cs_n(cs_n),.spi_sclk(sclk),.spi_mosi(mosi),.rst_n(rst_n),.ovr_armed(ovr_armed),.por_masked(por_masked));
 integer fails=0,checks=0,seed=7,rises=0,falls=0,arm_rises=0;
 reg mon=0;realtime t_rrise=0;
 task fail(input [1023:0] msg);begin
  fails=fails+1;$display("FAIL %0s (t=%0t)",msg,$time);
  if(fails>=25)begin $display("POR_PATH_FAIL %0d failing checks of %0d (stopped early)",fails,checks);$finish;end
 end endtask
 task chk(input ok,input [1023:0] msg);begin checks=checks+1;if(!ok)fail(msg);end endtask
 task edges(input integer r,f,input [1023:0] msg);begin
  checks=checks+1;
  if(rises!=r||falls!=f)begin $display("  rst_n edges %0d up / %0d down, expected %0d / %0d",rises,falls,r,f);fail(msg);end
  rises=0;falls=0;
 end endtask
 always @(posedge rst_n)if(mon)rises=rises+1;
 always @(negedge rst_n)if(mon)falls=falls+1;
 always @(posedge reset_n_pad)t_rrise=$realtime;
 // I1 / I2 (sampled after the zero-delay network has settled)
 always @(reset_n_pad or por_n or rst_n)if(mon)begin
  #0;#0;
  if(!reset_n_pad&&rst_n!==1'b0)fail("I1 rst_n not low with RESET_N low");
  if(por_n===1'b1&&rst_n!==reset_n_pad)fail("I2 rst_n differs from RESET_N with por_n high");
 end
 // I3 (1 ns allowance: the delayed-clock copy sets ovr 0.5 ns after the edge)
 always @(posedge ovr_armed)if(mon)begin
  arm_rises=arm_rises+1;
  if($realtime-t_rrise>1.0||!sclk||!reset_n_pad)fail("I3 override became effective without a RESET_N release that finds SCLK high");
 end

 // ---- power-up without any clock edge. The storage is deposited in a pin state in which no clear
 // is active (CS_N low, MOSI high, RESET_N high, SCLK high); the pins then go to the wanted levels
 // through falling edges of RESET_N / SCLK only, in one time step, so the DUT's own asynchronous
 // clears (a level in silicon, an edge in the simulator) act on the deposited state and neither
 // flop group sees a clock edge.
 task storage(input [15:0] k,input [1:0] o,input r,p,s,input c,ck,m);begin
  mosi=1;reset_n_pad=1;#1 sclk=1;cs_n=0;por_n=p;por_bypass=s;
  #1 dut.key=k;dut.ovr=o[1]?1'bx:o[0];
  #1 cs_n=c;mosi=m;reset_n_pad=r;sclk=ck;
  #1;
 end endtask
 task power_up(input integer init,input r,p,s,input c,ck,m);begin
  mon=0;
  case(init)
   0:storage(16'h0000,2'd0,r,p,s,c,ck,m);
   1:storage(16'hFFFF,2'd1,r,p,s,c,ck,m);
   2:storage(16'hxxxx,2'd2,r,p,s,c,ck,m);
   3:storage(KEY,2'd1,r,p,s,c,ck,m);
   default:storage(~KEY,2'd1,r,p,s,c,ck,m);
  endcase
  rises=0;falls=0;arm_rises=0;mon=1;
  #5;
 end endtask
 // ---- host
 // n bits of k (MSB first) with CS_N low; hold = 1: SCLK stays high after the last rising edge
 task shift_in(input [15:0] k,input integer n,input hold);integer b;begin
  for(b=n-1;b>=0;b=b-1)begin
   mosi=k[b];#20 sclk=1;#20;
   if(b!=0||!hold)begin sclk=0;#5;end
  end
 end endtask
 // rescue procedure of the RTL header, steps 1..7
 task rescue_key_with(input [15:0] k,input integer n);begin
  reset_n_pad=0;                 // 1
  #20 sclk=0;#20 cs_n=1;#20 mosi=0;// 2 idle
  #20 cs_n=0;#20;                // 3
  shift_in(k,n,1);               // 4 (SCLK left high)
  #20 mosi=1;                    //   (already high for the real key)
  #20 cs_n=1;                    // 5
  #50 reset_n_pad=1;             // 6
  #50 sclk=0;#50;                // 7
 end endtask
 task rescue_key;begin rescue_key_with(KEY,16);end endtask
 // the pre-review key: all three SPI pins high at a RESET_N rising edge, no bits shifted
 task old_key;begin
  reset_n_pad=0;#20 mosi=1;#5 cs_n=1;#5 sclk=1;#50 reset_n_pad=1;#50 sclk=0;#50;
 end endtask
 // Mode-0 transaction with random data. style 0: normal host (MOSI anything at the end, then low);
 // 1: rescue-mode bit-banged host (32 clocks, MOSI raised before CS_N rises);
 // 2: rescue-mode ordinary controller (40 clocks, last byte 0xFF, MOSI simply stays)
 task spi(input integer style);integer k;begin
  cs_n=0;#20;
  for(k=0;k<(style==2?40:32);k=k+1)begin mosi=(style==2&&k>=32)?1'b1:$random(seed);#20 sclk=1;#20 sclk=0;end
  if(style==1)begin #5 mosi=1;#15;end
  else if(style==0)begin #5 mosi=$random(seed);#15;end
  else #20;
  cs_n=1;#40;
  if(style==0)begin mosi=0;#20;end
 end endtask
 task traffic(input integer ntx,input integer style);integer j;begin
  for(j=0;j<ntx;j=j+1)spi(style);
 end endtask
 // RESET_N low pulse of w ns with the pins as given during and after it
 task reset_pulse(input real w,input c,k,m);begin
  cs_n=c;sclk=k;mosi=m;#10 reset_n_pad=0;#(w) reset_n_pad=1;#50;
 end endtask
 task noise(input integer n);integer q;begin
  for(q=0;q<n;q=q+1)begin {cs_n,sclk,mosi}=$random(seed);#7;end
 end endtask

 integer i,v,o,k,exp,nrel,b;reg ematch,eidle,elow,earm;reg[15:0] kk;
 reg [15:0] sub [0:39];
 initial begin
  if($value$plusargs("seed=%d",seed))begin end
  for(i=0;i<5;i=i+1)begin
   // ---- S1 healthy POR, RESET_N tied high, pins at the pull default
   power_up(i,1,0,0, 1,0,0);
   chk(rst_n===1'b0,"S1 reset not asserted during the POR pulse (RESET_N tied high)");
   #1000 chk(rst_n===1'b0&&ovr_armed===1'b0,"S1 reset lost during the POR pulse");
   por_n=1;#10 chk(rst_n===1'b1,"S1 no release after POR");edges(1,0,"S1 power-up");
   traffic(20,0);edges(0,0,"S1 normal traffic");
   noise(64);edges(0,0,"S1 arbitrary pin activity with a healthy POR");chk(arm_rises==0,"S1 override moved");
   cs_n=1;sclk=0;mosi=0;#20;
   por_n=0;#10 chk(rst_n===1'b0,"S1 brownout not honoured");#100 por_n=1;#10;edges(1,1,"S1 brownout");
   // brownout in the middle of a transaction (CS_N low, SCLK high, MOSI high)
   cs_n=0;#20 mosi=1;sclk=1;#5 por_n=0;#10 chk(rst_n===1'b0,"S1 brownout during a transaction not honoured");
   #100 por_n=1;#10 sclk=0;cs_n=1;mosi=0;#20;edges(1,1,"S1 brownout in traffic");
   // ---- S2 healthy POR, RESET_N driven: low through the ramp, released after the POR
   power_up(i,0,0,0, 1,0,0);
   #100 por_n=1;#100 chk(rst_n===1'b0,"S2 released while RESET_N low");
   reset_n_pad=1;#10 chk(rst_n===1'b1&&!ovr_armed,"S2 no release");edges(1,0,"S2 power-up");
   traffic(10,0);reset_pulse(100,1,0,0);edges(1,1,"S2 reset pulse");
   reset_pulse(0.001,1,0,0);edges(1,1,"S2 1 ps RESET_N pulse, healthy POR");
   // RESET_N low in the middle of traffic (clocks with CS_N low while in reset), healthy POR
   cs_n=0;#20 reset_n_pad=0;shift_in(16'h5A5A,16,0);shift_in(KEY,16,0);#20 reset_n_pad=1;#20 cs_n=1;mosi=0;#20;
   chk(rst_n===1'b1&&!ovr_armed,"S2 reset during traffic");edges(1,1,"S2 reset during traffic");
   // ---- S3 POR stuck low, no strap, RESET_N tied high, default pins: dead but in reset
   power_up(i,1,0,0, 1,0,0);
   #1000 chk(rst_n===1'b0,"S3 die out of reset with a dead POR and no override");
   traffic(10,0);edges(0,0,"S3 traffic");chk(rst_n===1'b0&&!ovr_armed&&!por_masked,"S3 state");
   // RESET_N pulses without the key do not release it either
   reset_pulse(100,1,0,0);reset_pulse(100,0,0,1);reset_pulse(100,0,0,0);cs_n=1;mosi=0;#20;
   edges(0,0,"S3 unkeyed RESET_N pulses");
   // the pre-review key (review P2): all SPI pins high at the RESET_N rising edge. No release.
   old_key;chk(rst_n===1'b0&&ovr_armed===1'b0&&por_masked===1'b0,"S3 all-pins-high RESET_N release armed the override (P2)");
   noise(40);cs_n=1;mosi=0;sclk=0;#20;edges(0,0,"S3 old key");
   // wrong keys: one bit wrong (all 16), 15 bits, 17 bits, bit-reversed, complement, 0, all ones
   for(b=0;b<16;b=b+1)begin rescue_key_with(KEY^(16'h1<<b),16);chk(rst_n===1'b0&&!ovr_armed,"S3 key with one wrong bit accepted");end
   rescue_key_with(KEY,15);chk(rst_n===1'b0,"S3 15-bit key accepted");
   reset_n_pad=0;#20 sclk=0;#20 cs_n=1;#20 mosi=0;#20 cs_n=0;#20 shift_in(KEY,16,0);shift_in(16'h0001,1,1);
   #20 cs_n=1;#50 reset_n_pad=1;#50 sclk=0;#50 chk(rst_n===1'b0,"S3 key followed by a 17th bit accepted");
   rescue_key_with(16'hA5C3,16);chk(rst_n===1'b0,"S3 bit-reversed key accepted");
   rescue_key_with(~KEY,16);chk(rst_n===1'b0,"S3 complement key accepted");
   rescue_key_with(16'h0000,16);chk(rst_n===1'b0,"S3 zero key accepted");
   rescue_key_with(16'hFFFF,16);chk(rst_n===1'b0,"S3 all-ones key accepted");
   // the key clocked in with RESET_N HIGH, then a RESET_N pulse with SCLK high: no release
   cs_n=1;mosi=0;sclk=0;#20 cs_n=0;#20 shift_in(KEY,16,1);#20 cs_n=1;reset_pulse(100,1,1,1);
   chk(rst_n===1'b0&&!ovr_armed,"S3 key shifted with RESET_N high accepted");
   // the key clocked in with CS_N HIGH (its zeros are the idle state)
   sclk=0;#20 mosi=0;#20 reset_n_pad=0;#20 shift_in(KEY,16,1);#50 reset_n_pad=1;#50 sclk=0;#50;
   chk(rst_n===1'b0&&!ovr_armed,"S3 key shifted with CS_N high accepted");
   // the right key, but SCLK low at the RESET_N rising edge
   reset_n_pad=0;#20 cs_n=1;#20 mosi=0;#20 cs_n=0;#20 shift_in(KEY,16,0);#20 cs_n=1;#50 reset_n_pad=1;#50;
   chk(rst_n===1'b0&&!ovr_armed,"S3 key with SCLK low at the RESET_N edge accepted");
   mosi=0;#20;edges(0,0,"S3 wrong keys");
   // ---- S4 POR stuck low, strap = 1 (first path): RESET_N is the reset
   power_up(i,0,0,1, 1,0,0);
   #100 chk(rst_n===1'b0,"S4 RESET_N low ignored");reset_n_pad=1;#10 chk(rst_n===1'b1&&por_masked===1'b1,"S4 strap does not release");
   traffic(10,0);reset_pulse(100,1,0,0);edges(2,1,"S4 strap");chk(!ovr_armed,"S4 override set");
   por_bypass=0;#10 chk(rst_n===1'b0&&por_masked===1'b0,"S4 strap removed");por_bypass=1;#10;edges(1,1,"S4 strap toggled");
   // ---- S5 POR stuck low, no strap: rescue through the second path
   power_up(i,1,0,0, 1,0,0);
   rescue_key;chk(rst_n===1'b1&&ovr_armed===1'b1&&por_masked===1'b1,"S5 keyed release did not start the die");
   edges(1,0,"S5 keyed release");chk(arm_rises==1,"S5 arm count");
   traffic(40,1);edges(0,0,"S5 rescue-mode traffic (bit-banged) glitched reset");
   traffic(40,2);edges(0,0,"S5 rescue-mode traffic (40 clocks, trailing FF) glitched reset");
   chk(rst_n===1'b1&&ovr_armed===1'b1,"S5 override lost in rescue-mode traffic");
   // SCLK toggling for another device while CS_N high (MOSI high)
   mosi=1;for(v=0;v<50;v=v+1)begin #20 sclk=1;#20 sclk=0;end
   edges(0,0,"S5 foreign clocks");
   // reset without re-keying: SCLK high, RESET_N pulse (key and ovr survive)
   #20 sclk=1;#20 reset_n_pad=0;#10 chk(rst_n===1'b0,"S5 RESET_N low in rescue mode");#90 reset_n_pad=1;#50 sclk=0;#50;
   chk(rst_n===1'b1&&ovr_armed===1'b1,"S5 reset pulse with SCLK high");edges(1,1,"S5 reset pulse with SCLK high");
   // RESET_N pulse with the bus at rest (SCLK low): clean reset, ovr gone, key kept: stays in reset
   reset_pulse(100,1,0,1);chk(rst_n===1'b0&&!ovr_armed,"S5 RESET_N pulse with SCLK low released the die");
   edges(0,1,"S5 RESET_N pulse with SCLK low");
   // short re-arm (the key survived): SCLK high, RESET_N low, RESET_N high, SCLK low
   #20 sclk=1;#20 reset_n_pad=0;#50 reset_n_pad=1;#50 sclk=0;#50;
   chk(rst_n===1'b1&&ovr_armed===1'b1,"S5 short re-arm");edges(1,0,"S5 short re-arm");
   // full re-key from the running state: one reset pulse
   rescue_key;chk(rst_n===1'b1,"S5 full re-key");edges(1,1,"S5 full re-key");
   // reset pulse mid-transaction (CS_N low, SCLK low): stays in reset, and rst_n must not blip
   // high at the RESET_N rising edge (H7)
   cs_n=0;#20 mosi=1;#20;reset_pulse(100,0,0,1);chk(rst_n===1'b0&&!ovr_armed,"S5 unkeyed reset pulse released the die");
   edges(0,1,"S5 unkeyed reset pulse (CS_N low)");
   #20 cs_n=1;#20;rescue_key;chk(rst_n===1'b1,"S5 re-key");edges(1,0,"S5 re-key");
   // RESET_N low while a transaction is clocked (key shifted away), SCLK high at the release:
   // the die must stay in reset (ovr survives, the key does not)
   cs_n=0;#20 mosi=1;#20 sclk=1;#20 reset_n_pad=0;#20 sclk=0;#20 sclk=1;#20 reset_n_pad=1;#50 sclk=0;#20 cs_n=1;#20;
   chk(rst_n===1'b0&&!ovr_armed,"S5 key survived clocks with RESET_N and CS_N low");edges(0,1,"S5 clocked reset pulse");
   // keying with foreign clocks (CS_N high, MOSI high) between the last bit and the release: key held
   reset_n_pad=0;#20 sclk=0;#20 cs_n=1;#20 mosi=0;#20 cs_n=0;#20 shift_in(KEY,16,0);
   #20 cs_n=1;for(v=0;v<5;v=v+1)begin #20 sclk=1;#20 sclk=0;end
   #20 sclk=1;#50 reset_n_pad=1;#50 sclk=0;#50;
   chk(rst_n===1'b1&&ovr_armed===1'b1,"S5 clocks with CS_N high changed the key");edges(1,0,"S5 key then foreign clocks");
   // 1 ps RESET_N pulse in rescue mode: zero-delay model clears ovr; die must end in reset, no re-release
   mosi=1;#20;reset_pulse(0.001,1,0,1);chk(rst_n===1'b0,"S5 RESET_N runt");edges(0,1,"S5 RESET_N runt");
   // ---- S6 dead-man violation: clean and permanent reset, both parts cleared
   rescue_key;edges(1,0,"S6 key");traffic(5,1);
   mosi=0;#10 chk(rst_n===1'b0&&!ovr_armed,"S6 idle (CS_N high, MOSI low) did not drop the override");
   chk(dut.ovr===1'b0&&dut.key===16'h0000,"S6 idle did not clear ovr and the key");
   traffic(30,0);mosi=1;#20 traffic(10,1);noise(64);
   chk(rst_n===1'b0,"S6 override came back without RESET_N");edges(0,1,"S6 after the violation");
   // RESET_N pulses with SCLK high (short re-arm / old key) must not bring it back: the key is gone
   cs_n=1;mosi=0;sclk=0;#20 mosi=1;#20 sclk=1;#20 reset_n_pad=0;#50 reset_n_pad=1;#50 sclk=0;#50;
   chk(rst_n===1'b0&&!ovr_armed,"S6 short re-arm after a dead-man violation released the die");
   old_key;chk(rst_n===1'b0&&!ovr_armed,"S6 old key after a dead-man violation released the die");edges(0,0,"S6 re-arm attempts");
   // 100 ps dead-man violation (CS_N leads MOSI): zero-delay model = permanent reset
   rescue_key;edges(1,0,"S6 key 2");cs_n=0;#20 mosi=0;#20 sclk=1;#20 sclk=0;#20 cs_n=1;#0.1 mosi=1;#50;
   chk(rst_n===1'b0,"S6 100 ps idle");edges(0,1,"S6 100 ps idle");
   // ---- S7 POR stuck high (never asserts): rst_n is RESET_N, whatever the pins do
   power_up(i,1,1,0, 1,0,0);
   chk(rst_n===1'b1,"S7");noise(64);
   reset_pulse(50,1,1,1);reset_pulse(50,1,0,0);reset_pulse(50,0,1,0);edges(3,3,"S7 POR stuck high");
   // ---- S9 healthy die: all pins high at the RESET_N release does nothing (P2); the full
   // procedure arms visibly, is harmless until a brownout, and is cleared by idle
   power_up(i,0,1,0, 1,0,0);
   #20 mosi=1;#5 sclk=1;#50 reset_n_pad=1;#50 chk(rst_n===1'b1&&ovr_armed===1'b0&&por_masked===1'b0,"S9 all pins high armed a healthy die (P2)");
   por_n=0;#10 chk(rst_n===1'b0,"S9 brownout with all SPI pins high not honoured (P2)");por_n=1;#10;
   sclk=0;#20 mosi=0;#20;edges(2,1,"S9 pins high");
   rescue_key;chk(rst_n===1'b1&&ovr_armed===1'b1&&por_masked===1'b0,"S9 arming not visible");
   por_n=0;#10 chk(rst_n===1'b1&&por_masked===1'b1,"S9 armed die: POR masked, visible");por_n=1;#10;
   mosi=0;#20 chk(ovr_armed===1'b0,"S9 idle did not disarm");
   por_n=0;#10 chk(rst_n===1'b0,"S9 brownout after disarm");por_n=1;#10;edges(2,2,"S9 armed");
   // ---- S11 non-idle power-up (review P1 / B2): RESET_N tied high, healthy POR asserted, host
   // pins NOT idle for the whole POR pulse (unpowered host clamps low; unconfigured FPGA pulls high;
   // MOSI idling high). Reset must hold in every storage state except the one stated residual
   // (init 3: key = KEY and ovr = 1), which is asserted as such.
   for(v=0;v<8;v=v+1)if(!(v[2]&&!v[0]))begin
    power_up(i,1,0,0, v[2],v[1],v[0]);
    if(i==3)begin
     chk(rst_n===1'b1&&ovr_armed===1'b1&&por_masked===1'b1,"S11 the stated residual state is not what the header says");
     por_n=1;#100 cs_n=1;#5 sclk=0;#5 mosi=0;#20 chk(ovr_armed===1'b0,"S11 residual not ended by idle");
     por_n=0;#10 chk(rst_n===1'b0,"S11 POR not honoured after the first idle");por_n=1;#10;
    end else if(i==2)begin
     // X storage: nothing clears it; the model cannot say more than "not a known release"
     chk(rst_n!==1'b1,"S11 X storage released reset");
    end else begin
     chk(rst_n===1'b0&&ovr_armed===1'b0&&por_masked===1'b0,"S11 reset released against an asserted POR at a non-idle power-up (P1)");
     #1000 chk(rst_n===1'b0,"S11 reset lost during the POR pulse");
     por_n=1;#10 chk(rst_n===1'b1,"S11 no release after the POR");edges(1,0,"S11 power-up");
     traffic(3,0);
     por_n=0;#10 chk(rst_n===1'b0,"S11 brownout");por_n=1;#10;edges(1,1,"S11 brownout");
    end
   end
  end
  // ---- S10 exhaustive static enumeration, no clock edge ever: ALL 2^17 storage states x 8 SPI pin
  // states x RESET_N, POR asserted, no strap. Reset is released in exactly the states
  //   key == KEY and ovr == 1 and not idle and RESET_N == 1          (6 of 2 097 152)
  // White box: the clears act as specified (idle clears key and ovr; RESET_N low & SCLK low clears ovr).
  mon=0;nrel=0;
  for(o=0;o<2;o=o+1)for(k=0;k<65536;k=k+1)for(v=0;v<16;v=v+1)begin
   storage(k[15:0],{1'b0,o[0]},v[3],1'b0,1'b0,v[2],v[1],v[0]);
   eidle=v[2]&&!v[0];elow=!v[3]&&!v[1];ematch=k[15:0]==KEY;earm=o[0]&&ematch&&!eidle&&!elow;
   checks=checks+1;
   if(rst_n!==(v[3]&&earm)||ovr_armed!==earm||por_masked!==earm||dut.ovr!==(o[0]&&!eidle&&!elow)||dut.key!==(eidle?16'h0000:k[15:0]))begin
    $display("  key=%h ovr=%0d RESET_N=%b CS_N=%b SCLK=%b MOSI=%b: rst_n=%b ovr_armed=%b por_masked=%b dut.ovr=%b dut.key=%h",
     k[15:0],o,v[3],v[2],v[1],v[0],rst_n,ovr_armed,por_masked,dut.ovr,dut.key);
    fail("S10 static enumeration");
   end
   if(rst_n===1'b1)begin nrel=nrel+1;
    $display("S10 released against an asserted POR: key=%h ovr=%0d RESET_N=%b CS_N=%b SCLK=%b MOSI=%b",k[15:0],o,v[3],v[2],v[1],v[0]);end
  end
  $display("S10 %0d of 2097152 (storage, pin) states release reset against an asserted POR",nrel);
  chk(nrel==6,"S10 number of releasing states is not 6");
  // ---- S12 all 64 input levels x a subset of storage states (incl. KEY and its 16 one-bit neighbours)
  sub[0]=16'h0000;sub[1]=16'hFFFF;sub[2]=KEY;sub[3]=~KEY;sub[4]=16'hA5C3;sub[5]=16'hA53C;sub[6]=KEY>>1;sub[7]=KEY<<1;
  for(b=0;b<16;b=b+1)sub[8+b]=KEY^(16'h1<<b);
  for(b=0;b<16;b=b+1)sub[24+b]=$random(seed);
  for(o=0;o<2;o=o+1)for(k=0;k<40;k=k+1)for(v=0;v<64;v=v+1)begin
   kk=sub[k];
   storage(kk,{1'b0,o[0]},v[5],v[4],v[3],v[2],v[1],v[0]);
   eidle=v[2]&&!v[0];elow=!v[5]&&!v[1];earm=o[0]&&kk==KEY&&!eidle&&!elow;
   checks=checks+1;
   if(rst_n!==(v[5]&&(v[4]||v[3]||earm))||ovr_armed!==earm||por_masked!==(!v[4]&&(v[3]||earm)))begin
    $display("  key=%h ovr=%0d RESET_N=%b por_n=%b strap=%b CS_N=%b SCLK=%b MOSI=%b: rst_n=%b ovr_armed=%b por_masked=%b",
     kk,o,v[5],v[4],v[3],v[2],v[1],v[0],rst_n,ovr_armed,por_masked);
    fail("S12 static table");
   end
  end
  if(fails==0)$display("POR_PATH_PASS %0d checks",checks);
  else $display("POR_PATH_FAIL %0d failing checks of %0d",fails,checks);
  $finish;
 end
endmodule
