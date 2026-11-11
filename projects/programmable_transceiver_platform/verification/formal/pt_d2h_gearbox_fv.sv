// Formal harness for the AC-1 D2H pad-edge path (rtl/pt_host_link.sv), transport rework
// 2026-11-10: the hddr-domain reset release and hcore divider (pt_host_divider) and the 4:1
// gearbox / DDR launch / forwarded clock (pt_d2h_gearbox) with an arbitrary prefix stream on the
// generated core clock. multiclock: the only free clock is the hddr input `clk`.
// Proven:
//  (1) the pin equals a reference model that takes the prefix quad at each hcore rising edge (the
//      value from before the edge) and launches P0,P1 (next hddr rising and falling edges) then
//      P2,P3, i.e. the pin carries w_k = P_k ^ P_(k-1) in order;
//  (2) the prefix register (hcore) changes only on hcore rising edges, which coincide with hddr
//      rising edges, and the gearbox hold register x samples it only on those edges (two hddr
//      periods after it changed): SDC multicycle 2 hcore -> host.gearbox.x;
//  (3) on every falling edge, the register selected into q_f (x when nsel, else f3) did not change
//      on the rising edge half a period before: SDC multicycle 2 (1.5 periods) x/f3 -> q_f;
//  (4) the forwarded clock pin is 1 after every enabled rising edge and 0 after every falling edge;
//  (5) all of the above also hold when the falling-edge flops leave reset one falling edge late
//      (the untimed half-period recovery case): `late` chooses the release edge.
module pt_d2h_gearbox_fv(input wire clk,rst_n,input wire[39:0]next_prefix,input wire en);
 (* anyconst *) reg late;
 reg[1:0]drs;
 always @(posedge clk or negedge rst_n)if(!rst_n)drs<=0;else drs<={drs[0],1'b1};
 wire dr_n=drs[1];
 reg ndr_late;   // dr_n delayed to the next falling edge
 always @(negedge clk or negedge rst_n)if(!rst_n)ndr_late<=0;else ndr_late<=dr_n;
 wire nrst_n=late?(dr_n&&ndr_late):dr_n;
 wire core_clk;wire[9:0]pin;wire cpin;
 pt_host_divider divider(.clk(clk),.rst_n(dr_n),.core_clk(core_clk));
 reg[39:0]prefix;
 always @(posedge core_clk or negedge dr_n)if(!dr_n)prefix<=0;else prefix<=next_prefix;
 pt_d2h_gearbox gearbox(.ddr_clk(clk),.rst_n(dr_n),.nrst_n(nrst_n),.prefix(prefix),.clk_en(en),.d2h_pin(pin),.clk_pin(cpin));
 reg init=1;
 reg[39:0]mx;reg[9:0]mr,mf,mq;
 always @($global_clock)begin
  init<=0;
  if(init)assume(!rst_n);
  if(!init&&!$stable(rst_n))assume($stable(clk)&&rst_n);   // one reset, released between edges
  if(!dr_n)begin mx<=0;mr<=0;mf<=0;mq<=0;end
  else begin
   if($rose(core_clk))begin mx<=$past(prefix);mr<=mx[29:20];mf<=mx[39:30];end
   else if($rose(clk))begin mr<=mx[9:0];mf<=mx[19:10];end
   if($fell(clk))mq<=mf;
  end
 end
 // (3) is asserted inside pt_d2h_gearbox (`ifdef FORMAL), where x/f3/nsel are visible.
 reg[3:0]rises=0;
 always @(posedge clk)if(!dr_n)rises<=0;else if(rises!=15)rises<=rises+1'b1;
 always @($global_clock)if(!init&&dr_n&&$past(dr_n))begin
  // global-clock registers update one step after the clocked RTL flops: compare one step late
  if($past(dr_n,2)&&rises>=3)assert($past(pin)==(mr^mq));
  if(!$rose(core_clk))assert($stable(prefix));
  if($rose(core_clk))assert($rose(clk));
  // (4) forwarded clock: low after every falling edge, high after an enabled rising edge
  if(rises>=3&&nrst_n&&$fell(clk))assert(!cpin);
  if(rises>=3&&$rose(clk)&&$past(en))cover(cpin);
  cover($rose(core_clk)&&mx!=0&&pin!=0);
  cover(late&&rises>=4&&pin!=0);
 end
endmodule
