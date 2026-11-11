// Stimulus/dump bench for rtl/pt_interp2x.sv (checked by verification/check_interp2x.py):
// phase 1 halfband (rf_tx_clk 80 MHz): a complex tone in 12-bit samples with valid gaps, then a
// full-scale square burst (saturation); phase 2 bypass (40 MHz): pass-through.
`timescale 1ps/1ps
module tb_pt_interp2x;
 reg rst_n=0,clk=0,hb=1;integer half_ps=6250;
 always #(half_ps) clk=~clk;
 wire core_clk,ov;wire[23:0]os;reg[23:0]is=0;reg iv=0;
 pt_interp2x dut(.rst_n(rst_n),.clk_fast(clk),.halfband(hb),.core_clk(core_clk),.in_sample(is),.in_valid(iv),.out_sample(os),.out_valid(ov));
 integer fi,fo,n=0,f_tone,ti,tq;real ph;
 // inputs change after each core edge; log the value present at the core edge
 always @(posedge core_clk) $fdisplay(fi,"%0d %0d %0d %0d",hb,iv,$signed(is[11:0]),$signed(is[23:12]));
 always @(posedge clk) $fdisplay(fo,"%0d %0d %0d %0d",hb,ov,$signed(os[11:0]),$signed(os[23:12]));
 task drive(input integer cycles,input integer mode);integer k;begin
  for(k=0;k<cycles;k=k+1)begin
   @(posedge core_clk);#1000;
   ph=6.283185307179586*n*10.0/40.0;n=n+1;
   case(mode)
    0:begin iv=((n%97)<90);ti=$rtoi(1700.0*$cos(ph));tq=$rtoi(1700.0*$sin(ph));is={tq[11:0],ti[11:0]};end // 10 MHz complex tone, gaps
    1:begin iv=1;is=((n/8)%2)?{12'sd2047,-12'sd2048}:{-12'sd2048,12'sd2047};end // square, saturating overshoot
    2:begin iv=($random%5)!=0;is=$random;end                                     // random (bypass)
   endcase
  end end endtask
 initial begin
  fi=$fopen("interp_in.txt","w");fo=$fopen("interp_out.txt","w");
  #20000 rst_n=1;
  drive(4096,0);drive(256,1);
  @(posedge core_clk);#1000;iv=0;is=0;repeat(20)@(posedge clk);
  rst_n=0;hb=0;half_ps=12500;#100000 rst_n=1;
  drive(512,2);
  $fclose(fi);$fclose(fo);$display("INTERP2X_DUMPED");$finish;
 end
endmodule
