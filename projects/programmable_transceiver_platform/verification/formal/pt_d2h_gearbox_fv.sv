// Formal harness for the AC-1 D2H pad-edge path (rtl/pt_host_link.sv), transport rework
// 2026-11-10: the hddr-domain reset release and hcore divider (pt_host_divider) and the 4:1
// gearbox / DDR launch / forwarded clock (pt_d2h_gearbox) with an arbitrary prefix stream on the
// generated core clock. multiclock: the only free clock is the hddr input `clk`.
// D2H ping-pong hand-over (DG8-6): pt_d2h_pingpong (hcore) computes the prefix of an arbitrary word
// stream w into two alternate entries; core_rst_n releases zero to two hcore edges after the divider
// (anyconst `cl`), the write index has the divider's reset.
// Proven:
//  (1) the pin equals a reference model that takes, at each hcore rising edge, the prefix quad of the
//      stream as it stood two hcore edges earlier (one hcore period of hand-over latency) and launches
//      P0,P1 (next hddr rising and falling edges) then P2,P3, i.e. the pin carries w_k = P_k ^ P_(k-1)
//      in order. A gearbox reading the entry written at the previous edge (one period window) or a
//      wrong read-select phase fails (1);
//  (2) the ping-pong entries change only on hcore rising edges, which coincide with hddr rising edges,
//      and the entry the gearbox reads at a load edge is the one this edge overwrites, so its value was
//      written two hcore edges (four hddr periods) before: SDC multicycle 4 hcore -> host.gearbox.x / hr;
//  (3) on every falling edge, the register selected into q_f (x when nsel, else f3) did not change
//      on the rising edge half a period before: SDC multicycle 2 (1.5 periods) x/f3 -> q_f;
//  (4) the forwarded clock pin is 1 after every enabled rising edge and 0 after every falling edge;
//  (5) all of the above also hold when the falling-edge flops leave reset one falling edge late
//      (the untimed half-period recovery case): `late` chooses the release edge;
//  (6) and with reset asserted again at any time while running (any number of resets).
module pt_d2h_gearbox_fv(input wire clk,rst_n,input wire[39:0]w,input wire en);
 (* anyconst *) reg late;
 (* anyconst *) reg[1:0]cl;
 reg[1:0]drs;
 always @(posedge clk or negedge rst_n)if(!rst_n)drs<=0;else drs<={drs[0],1'b1};
 wire dr_n=drs[1];
 reg ndr_late;   // dr_n delayed to the next falling edge
 always @(negedge clk or negedge rst_n)if(!rst_n)ndr_late<=0;else ndr_late<=dr_n;
 wire nrst_n=late?(dr_n&&ndr_late):dr_n;
 wire core_clk;wire[9:0]pin;wire cpin;
 pt_host_divider divider(.clk(clk),.rst_n(dr_n),.core_clk(core_clk));
 // core reset: released cl (0..2) hcore edges after the divider starts
 reg[1:0]crs;
 always @(posedge core_clk or negedge dr_n)if(!dr_n)crs<=0;else if(crs!=3)crs<=crs+1'b1;
 wire crst_n=dr_n&&(crs>=cl);
 wire[39:0]pp0,pp1;
 pt_d2h_pingpong pingpong(.core_clk(core_clk),.wrst_n(dr_n),.rst_n(crst_n),.w(w),.pp0(pp0),.pp1(pp1));
 // reference: the plain one-register prefix of the same stream, and its value one hcore edge older
 reg[39:0]prefix,pd;
 wire[9:0]c=prefix[39:30];
 wire[39:0]nx={c^w[0+:10]^w[10+:10]^w[20+:10]^w[30+:10],c^w[0+:10]^w[10+:10]^w[20+:10],c^w[0+:10]^w[10+:10],c^w[0+:10]};
 always @(posedge core_clk or negedge crst_n)if(!crst_n)begin prefix<=0;pd<=0;end else begin prefix<=nx;pd<=prefix;end
 pt_d2h_gearbox gearbox(.ddr_clk(clk),.rst_n(dr_n),.nrst_n(nrst_n),.pp0(pp0),.pp1(pp1),.clk_en(en),.d2h_pin(pin),.clk_pin(cpin));
 reg init=1;
 reg[39:0]mx;reg[9:0]mr,mf,mq;
 always @($global_clock)begin
  init<=0;
  if(init)assume(!rst_n);
  if(!init&&!$stable(rst_n))assume($stable(clk));   // resets assert and release between edges, any number of times
  if(!dr_n)begin mx<=0;mr<=0;mf<=0;mq<=0;end
  else begin
   if($rose(core_clk))begin mx<=$past(pd);mr<=mx[29:20];mf<=mx[39:30];end
   else if($rose(clk))begin mr<=mx[9:0];mf<=mx[19:10];end
   if($fell(clk))mq<=mf;
  end
 end
 // (3) is asserted inside pt_d2h_gearbox (`ifdef FORMAL), where x/f3/nsel are visible.
 reg[3:0]rises=0;
 reg[1:0]nres=0;   // reset releases seen
 always @($global_clock)if($rose(rst_n)&&nres!=3)nres<=nres+1'b1;
 always @(posedge clk)if(!dr_n)rises<=0;else if(rises!=15)rises<=rises+1'b1;
 always @($global_clock)if(!init&&dr_n&&$past(dr_n))begin
  // global-clock registers update one step after the clocked RTL flops: compare one step late
  if($past(dr_n,2)&&rises>=3)assert($past(pin)==(mr^mq));
  if(!$rose(core_clk))assert($stable(pp0)&&$stable(pp1));
  // (2) at each hcore edge one entry holds the stream prefix and the other its value one edge older
  if(!$rose(core_clk))assert((pp0==prefix&&pp1==pd)||(pp1==prefix&&pp0==pd));
  if($rose(core_clk))assert($rose(clk));
  // (4) forwarded clock: low after every falling edge, high after an enabled rising edge
  if(rises>=3&&nrst_n&&$fell(clk))assert(!cpin);
  if(rises>=3&&$rose(clk)&&$past(en))cover(cpin);
  cover($rose(core_clk)&&mx!=0&&pin!=0);
  cover(late&&rises>=4&&pin!=0);
  cover(nres>=2&&rises>=4&&pin!=0);   // data after a reset re-asserted while running
 end
endmodule
