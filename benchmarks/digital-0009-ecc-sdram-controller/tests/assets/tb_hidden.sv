`timescale 1ns/1ps
module tb_hidden;
  logic clk=0,rst_n=0; always #5 clk=~clk;
  logic reqv=0,reqr,reqw; logic [21:0] reqa; logic [63:0] reqwd; logic [7:0] reqs;
  logic rspv,rspr=1; logic [63:0] rsprd; logic corr,unc,init;
  logic cke,csn,rasn,casn,wen; logic [1:0] ba; logic [12:0] a; logic [3:0] dqm;
  tri [31:0] dq; logic [31:0] dq_drv; logic dq_oe;
  assign dq=dq_oe?dq_drv:32'bz;
  ecc_sdram_controller #(.INIT_WAIT_CYCLES(8),.REFRESH_CYCLES(96)) dut(
    .clk_i(clk), .rst_ni(rst_n), .req_valid_i(reqv), .req_ready_o(reqr),
    .req_write_i(reqw), .req_addr_i(reqa), .req_wdata_i(reqwd), .req_wstrb_i(reqs),
    .rsp_valid_o(rspv), .rsp_ready_i(rspr), .rsp_rdata_o(rsprd),
    .rsp_corrected_o(corr), .rsp_uncorrectable_o(unc), .init_done_o(init),
    .sdram_cke_o(cke), .sdram_cs_no(csn), .sdram_ras_no(rasn),
    .sdram_cas_no(casn), .sdram_we_no(wen), .sdram_ba_o(ba),
    .sdram_a_o(a), .sdram_dqm_o(dqm), .sdram_dq_io(dq)
  );
  logic [31:0] mem[0:16383]; logic [12:0] row[0:3];
  logic [31:0] rd0,rd1; logic rv0=0,rv1=0; integer idx;
  integer pre_count=0,ref_count=0,mrs_count=0;
  always_comb begin dq_oe=rv1;dq_drv=rd1;end
  always @(posedge clk) begin
    rv1<=rv0;rd1<=rd0;rv0<=0;
    if(!csn&&!rasn&&casn&&!wen&&a[10])pre_count<=pre_count+1;
    if(!csn&&!rasn&&!casn&&wen)ref_count<=ref_count+1;
    if(!csn&&!rasn&&!casn&&!wen)mrs_count<=mrs_count+1;
    if(!csn&&!rasn&&casn&&wen)row[ba]<=a;
    if(!csn&&rasn&&!casn)begin
      idx={row[ba],ba,a[8:0]};
      if(wen)begin rd0<=mem[idx];rv0<=1;end
      else if(!dqm)mem[idx]<=dq;
    end
  end
  task automatic request(input bit wr,input [21:0] ad,input [63:0] data,input [7:0] st);
    begin while(rspv)@(negedge clk);@(negedge clk);reqw=wr;reqa=ad;reqwd=data;reqs=st;reqv=1;
      while(!reqr)@(negedge clk);@(negedge clk);reqv=0;while(!rspv)@(negedge clk);end
  endtask
  task automatic flip(input integer base,input integer bitno);
    begin
      if(bitno<32)mem[base]=mem[base]^(32'b1<<bitno);
      else if(bitno<64)mem[base+1]=mem[base+1]^(32'b1<<(bitno-32));
      else mem[base+2]=mem[base+2]^(32'b1<<(bitno-64));
    end
  endtask
  integer bitno,refs_before; reg [31:0] keep0,keep1,keep2;
  localparam [63:0] PAT=64'hd36a_59c7_812e_f40b;
  initial begin
    repeat(3)@(posedge clk);rst_n=1;wait(init);@(negedge clk);
    if(pre_count!=1||ref_count!=2||mrs_count!=1)$fatal(1,"init sequence");
    request(1,22'd23,PAT,8'hff);if(corr||unc)$fatal(1,"write response");
    request(0,22'd23,0,0);if(rsprd!==PAT||corr||unc)$fatal(1,"clean");
    for(bitno=0;bitno<72;bitno=bitno+1)begin
      request(1,22'd23,PAT,8'hff);flip(69,bitno);request(0,22'd23,0,0);
      if(rsprd!==PAT||!corr||unc)$fatal(1,"single bit %0d",bitno);
    end
    request(1,22'd23,PAT,8'hff);flip(69,4);flip(69,61);request(0,22'd23,0,0);
    if(!unc||corr)$fatal(1,"double detect");
    keep0=mem[69];keep1=mem[70];keep2=mem[71];
    request(1,22'd23,64'hffff_ffff_ffff_ffff,8'h01);
    if(!unc||mem[69]!==keep0||mem[70]!==keep1||mem[71]!==keep2)$fatal(1,"bad rmw wrote");
    request(1,22'd170,64'h0123_4567_89ab_cdef,8'hff);
    request(0,22'd170,0,0);if(rsprd!==64'h0123_4567_89ab_cdef)$fatal(1,"boundary");
    request(1,22'd170,64'hffee_ddcc_bbaa_9988,8'b00111100);
    request(0,22'd170,0,0);if(rsprd!==64'h0123_ddcc_bbaa_cdef)$fatal(1,"rmw");
    while(rspv)@(negedge clk);rspr=0;@(negedge clk);reqw=0;reqa=170;reqv=1;while(!reqr)@(negedge clk);
    @(negedge clk);reqv=0;while(!rspv)@(negedge clk);
    repeat(5)begin @(negedge clk);if(!rspv||rsprd!==64'h0123_ddcc_bbaa_cdef)$fatal(1,"backpressure");end
    rspr=1;@(negedge clk);
    refs_before=ref_count;repeat(130)@(posedge clk);if(ref_count<=refs_before)$fatal(1,"refresh");
    rst_n=0;#2;if(init||reqr||rspv||cke)$fatal(1,"reset");
    $display("HIDDEN_PASS");$finish;
  end
  initial begin #1000000;$fatal(1,"timeout");end
endmodule
