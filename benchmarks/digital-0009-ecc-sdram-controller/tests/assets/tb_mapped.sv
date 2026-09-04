`timescale 1ns/1ps
module tb_mapped;
  logic clk=0,rst_n=0; always #5 clk=~clk;
  logic reqv=0,reqr,reqw; logic [21:0] reqa; logic [63:0] reqwd; logic [7:0] reqs;
  logic rspv,rspr=1; logic [63:0] rsprd; logic corr,unc,init;
  logic cke,csn,rasn,casn,wen; logic [1:0] ba; logic [12:0] a; logic [3:0] dqm;
  tri [31:0] dq; logic [31:0] dq_drv; logic dq_oe;
  assign dq=dq_oe?dq_drv:32'bz;
  ecc_sdram_controller dut(
    .clk_i(clk), .rst_ni(rst_n), .req_valid_i(reqv), .req_ready_o(reqr),
    .req_write_i(reqw), .req_addr_i(reqa), .req_wdata_i(reqwd), .req_wstrb_i(reqs),
    .rsp_valid_o(rspv), .rsp_ready_i(rspr), .rsp_rdata_o(rsprd),
    .rsp_corrected_o(corr), .rsp_uncorrectable_o(unc), .init_done_o(init),
    .sdram_cke_o(cke), .sdram_cs_no(csn), .sdram_ras_no(rasn),
    .sdram_cas_no(casn), .sdram_we_no(wen), .sdram_ba_o(ba),
    .sdram_a_o(a), .sdram_dqm_o(dqm), .sdram_dq_io(dq)
  );
  logic [31:0] mem[0:63];logic [12:0] row[0:3];logic [31:0] rd0,rd1;logic rv0=0,rv1=0;integer idx;
  always_comb begin dq_oe=rv1;dq_drv=rd1;end
  always @(posedge clk) begin
    rv1<=rv0;rd1<=rd0;rv0<=0;
    if(!csn&&!rasn&&casn&&wen)row[ba]<=a;
    if(!csn&&rasn&&!casn)begin
      idx={row[ba],ba,a[8:0]};
      if(wen)begin rd0<=mem[idx];rv0<=1;end else if(!dqm)mem[idx]<=dq;
    end
  end
  task request(input bit wr,input [63:0] data);
    begin while(rspv)@(negedge clk);@(negedge clk);reqw=wr;reqa=3;reqwd=data;reqs=8'hff;reqv=1;
      while(!reqr)@(negedge clk);@(negedge clk);reqv=0;while(!rspv)@(negedge clk);end
  endtask
  initial begin
    repeat(3)@(posedge clk);rst_n=1;wait(init);
    request(1,64'hcafe_f00d_1234_5678);request(0,0);
    if(rsprd!==64'hcafe_f00d_1234_5678||corr||unc)
      $fatal(1,"mapped readback data=%h corr=%b unc=%b words=%h/%h/%h",rsprd,corr,unc,mem[9],mem[10],mem[11]);
    $display("MAPPED_PASS");$finish;
  end
  initial begin #500000;$fatal(1,"timeout");end
endmodule
