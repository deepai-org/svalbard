module ecc_sdram_controller #(
  parameter int INIT_WAIT_CYCLES=10000, parameter int REFRESH_CYCLES=780
) (
  input logic clk_i,input logic rst_ni,input logic req_valid_i,output logic req_ready_o,
  input logic req_write_i,input logic [21:0] req_addr_i,input logic [63:0] req_wdata_i,
  input logic [7:0] req_wstrb_i,output logic rsp_valid_o,input logic rsp_ready_i,
  output logic [63:0] rsp_rdata_o,output logic rsp_corrected_o,
  output logic rsp_uncorrectable_o,output logic init_done_o,output logic sdram_cke_o,
  output logic sdram_cs_no,output logic sdram_ras_no,output logic sdram_cas_no,
  output logic sdram_we_no,output logic [1:0] sdram_ba_o,output logic [12:0] sdram_a_o,
  output logic [3:0] sdram_dqm_o,inout wire [31:0] sdram_dq_io
);
  assign req_ready_o=0; assign rsp_valid_o=0; assign rsp_rdata_o=0;
  assign rsp_corrected_o=0; assign rsp_uncorrectable_o=0; assign init_done_o=0;
  assign sdram_cke_o=0; assign sdram_cs_no=1; assign sdram_ras_no=1;
  assign sdram_cas_no=1; assign sdram_we_no=1; assign sdram_ba_o=0;
  assign sdram_a_o=0; assign sdram_dqm_o=4'hf; assign sdram_dq_io=32'bz;
endmodule
