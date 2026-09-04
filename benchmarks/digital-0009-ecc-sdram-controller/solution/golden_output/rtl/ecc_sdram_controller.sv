module ecc_sdram_controller #(
  parameter int INIT_WAIT_CYCLES = 10000,
  parameter int REFRESH_CYCLES = 780
) (
  input logic clk_i, input logic rst_ni,
  input logic req_valid_i, output logic req_ready_o,
  input logic req_write_i, input logic [21:0] req_addr_i,
  input logic [63:0] req_wdata_i, input logic [7:0] req_wstrb_i,
  output logic rsp_valid_o, input logic rsp_ready_i,
  output logic [63:0] rsp_rdata_o,
  output logic rsp_corrected_o, output logic rsp_uncorrectable_o,
  output logic init_done_o, output logic sdram_cke_o,
  output logic sdram_cs_no, output logic sdram_ras_no,
  output logic sdram_cas_no, output logic sdram_we_no,
  output logic [1:0] sdram_ba_o, output logic [12:0] sdram_a_o,
  output logic [3:0] sdram_dqm_o, inout wire [31:0] sdram_dq_io
);
  typedef enum logic [4:0] {
    ST_WAIT, ST_INIT_NOP, ST_INIT_PRE, ST_INIT_GAP1,
    ST_INIT_REF1, ST_INIT_RFC1, ST_INIT_REF2, ST_INIT_RFC2,
    ST_INIT_MRS, ST_INIT_MRD, ST_READY, ST_ADDR, ST_REFRESH, ST_RFC1, ST_RFC2,
    ST_ACT, ST_RCD, ST_ACCESS, ST_RD_WAIT1, ST_RD_WAIT2,
    ST_WR_GAP1, ST_WR_GAP2, ST_ECC_SYNDROME,
    ST_ECC_DECODE, ST_ECC_DECIDE, ST_ENCODE, ST_ENCODE_PARTS,
    ST_ENCODE_COMBINE, ST_ENCODE_FINISH, ST_RESP
  } state_t;
  (* fsm_encoding = "one-hot" *) state_t state;

  logic [15:0] init_count;
  logic [15:0] refresh_count;
  logic [21:0] addr_q;
  logic [23:0] physical_q;
  logic write_q, access_read_q;
  logic [63:0] wdata_q;
  logic [7:0] wstrb_q;
  logic [63:0] write_mask_q;
  logic [1:0] beat_q;
  logic [71:0] codeword_q;
  logic [63:0] encode_data_q;
  logic [70:0] hamming_q;
  logic [6:0] encode_part0_q, encode_part1_q, encode_part2_q, encode_part3_q;
  logic [3:0] encode_overall_parts_q;
  logic [6:0] encode_parity_q;
  logic encode_data_overall_q;
  logic [6:0] syndrome_q;
  logic overall_q;
  logic [63:0] decoded_q;
  logic [31:0] dq_out;
  logic dq_oe;
  wire [31:0] dq_in = sdram_dq_io;
  wire [31:0] current_read = dq_in;
  wire [23:0] physical_base = {2'b0, addr_q} + ({2'b0, addr_q} << 1);

  function automatic [70:0] ecc_place_data(input logic [63:0] data);
    logic [70:0] h;
    integer pos, di;
    begin
      h = 0; di = 0;
      for (pos = 1; pos <= 71; pos = pos + 1) begin
        if ((pos & (pos-1)) != 0) begin h[pos-1] = data[di]; di = di + 1; end
      end
      ecc_place_data = h;
    end
  endfunction

  function automatic [6:0] ecc_syndrome(input logic [71:0] cw);
    begin
      ecc_syndrome[0] = ^(cw[70:0] & 71'h555555555555555555);
      ecc_syndrome[1] = ^(cw[70:0] & 71'h666666666666666666);
      ecc_syndrome[2] = ^(cw[70:0] & 71'h787878787878787878);
      ecc_syndrome[3] = ^(cw[70:0] & 71'h007f807f807f807f80);
      ecc_syndrome[4] = ^(cw[70:0] & 71'h007fff80007fff8000);
      ecc_syndrome[5] = ^(cw[70:0] & 71'h007fffffff80000000);
      ecc_syndrome[6] = ^(cw[70:0] & 71'h7f8000000000000000);
    end
  endfunction

  function automatic [63:0] ecc_data(
    input logic [71:0] cw, input logic [6:0] syn, input logic overall
  );
    integer pos, di;
    begin
      ecc_data = 0; di = 0;
      for (pos = 1; pos <= 71; pos = pos + 1) begin
        if ((pos & (pos-1)) != 0) begin
          ecc_data[di] = cw[pos-1] ^ (overall && (syn == pos));
          di = di + 1;
        end
      end
    end
  endfunction

  function automatic [63:0] merge_bytes(
    input logic [63:0] old_data, input logic [63:0] new_data,
    input logic [63:0] write_mask
  );
    begin
      merge_bytes = (old_data & ~write_mask) | (new_data & write_mask);
    end
  endfunction

  logic [71:0] assembled;
  always_comb begin
    assembled = codeword_q;
    case (beat_q)
      0: assembled[31:0] = current_read;
      1: assembled[63:32] = current_read;
      default: assembled[71:64] = current_read[7:0];
    endcase
  end

  wire [6:0] assembled_syndrome = ecc_syndrome(codeword_q);
  wire [63:0] decoded_data = ecc_data(codeword_q, syndrome_q, overall_q);
  wire [63:0] merged_data = merge_bytes(decoded_q, wdata_q, write_mask_q);
  localparam logic [70:0] PM0=71'h555555555555555555;
  localparam logic [70:0] PM1=71'h666666666666666666;
  localparam logic [70:0] PM2=71'h787878787878787878;
  localparam logic [70:0] PM3=71'h007f807f807f807f80;
  localparam logic [70:0] PM4=71'h007fff80007fff8000;
  localparam logic [70:0] PM5=71'h007fffffff80000000;
  localparam logic [70:0] PM6=71'h7f8000000000000000;
  wire [70:0] placed_data = ecc_place_data(encode_data_q);
  wire [6:0] encode_part0 = {^(hamming_q[17:0]&PM6[17:0]),^(hamming_q[17:0]&PM5[17:0]),^(hamming_q[17:0]&PM4[17:0]),^(hamming_q[17:0]&PM3[17:0]),^(hamming_q[17:0]&PM2[17:0]),^(hamming_q[17:0]&PM1[17:0]),^(hamming_q[17:0]&PM0[17:0])};
  wire [6:0] encode_part1 = {^(hamming_q[35:18]&PM6[35:18]),^(hamming_q[35:18]&PM5[35:18]),^(hamming_q[35:18]&PM4[35:18]),^(hamming_q[35:18]&PM3[35:18]),^(hamming_q[35:18]&PM2[35:18]),^(hamming_q[35:18]&PM1[35:18]),^(hamming_q[35:18]&PM0[35:18])};
  wire [6:0] encode_part2 = {^(hamming_q[53:36]&PM6[53:36]),^(hamming_q[53:36]&PM5[53:36]),^(hamming_q[53:36]&PM4[53:36]),^(hamming_q[53:36]&PM3[53:36]),^(hamming_q[53:36]&PM2[53:36]),^(hamming_q[53:36]&PM1[53:36]),^(hamming_q[53:36]&PM0[53:36])};
  wire [6:0] encode_part3 = {^(hamming_q[70:54]&PM6[70:54]),^(hamming_q[70:54]&PM5[70:54]),^(hamming_q[70:54]&PM4[70:54]),^(hamming_q[70:54]&PM3[70:54]),^(hamming_q[70:54]&PM2[70:54]),^(hamming_q[70:54]&PM1[70:54]),^(hamming_q[70:54]&PM0[70:54])};
  logic [71:0] encoded_word;
  always_comb begin
    encoded_word={encode_data_overall_q ^ (^encode_parity_q),hamming_q};
    encoded_word[0]=encode_parity_q[0]; encoded_word[1]=encode_parity_q[1];
    encoded_word[3]=encode_parity_q[2]; encoded_word[7]=encode_parity_q[3];
    encoded_word[15]=encode_parity_q[4]; encoded_word[31]=encode_parity_q[5];
    encoded_word[63]=encode_parity_q[6];
  end

  assign sdram_dq_io = dq_oe ? dq_out : 32'bz;
  always_comb begin
    req_ready_o = rst_ni && (state == ST_READY) &&
                  (refresh_count + 32 < REFRESH_CYCLES);
    sdram_cke_o = (state != ST_WAIT);
    sdram_cs_no = !sdram_cke_o;
    sdram_ras_no = 1;
    sdram_cas_no = 1;
    sdram_we_no = 1;
    sdram_ba_o = physical_q[10:9];
    sdram_a_o = physical_q[23:11];
    sdram_dqm_o = 4'hf;
    dq_oe = 0;
    dq_out = 0;
    case (state)
      ST_INIT_PRE: begin sdram_cs_no=0; sdram_ras_no=0; sdram_we_no=0; sdram_a_o=13'h400; end
      ST_INIT_REF1, ST_INIT_REF2, ST_REFRESH: begin
        sdram_cs_no=0; sdram_ras_no=0; sdram_cas_no=0; sdram_we_no=1;
      end
      ST_INIT_MRS: begin
        sdram_cs_no=0; sdram_ras_no=0; sdram_cas_no=0; sdram_we_no=0;
        sdram_ba_o=0; sdram_a_o=13'h020;
      end
      ST_ACT: begin
        sdram_cs_no=0; sdram_ras_no=0; sdram_cas_no=1; sdram_we_no=1;
      end
      ST_ACCESS: begin
        sdram_cs_no=0; sdram_ras_no=1; sdram_cas_no=0;
        sdram_a_o=13'h400 | {4'b0,physical_q[8:0]};
        sdram_dqm_o=0;
        if (access_read_q) sdram_we_no=1;
        else begin
          sdram_we_no=0; dq_oe=1;
          case (beat_q)
            0: dq_out=codeword_q[31:0];
            1: dq_out=codeword_q[63:32];
            default: dq_out={24'b0,codeword_q[71:64]};
          endcase
        end
      end
      default: begin end
    endcase
  end

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      state <= ST_WAIT; init_count <= 0; refresh_count <= 0;
      init_done_o <= 0; addr_q <= 0; physical_q <= 0;
      write_q <= 0; access_read_q <= 0;
      wdata_q <= 0; wstrb_q <= 0; write_mask_q <= 0;
      beat_q <= 0; codeword_q <= 0; encode_data_q <= 0;
      hamming_q <= 0; encode_part0_q <= 0; encode_part1_q <= 0;
      encode_part2_q <= 0; encode_part3_q <= 0; encode_overall_parts_q <= 0;
      encode_parity_q <= 0; encode_data_overall_q <= 0;
      syndrome_q <= 0; overall_q <= 0; decoded_q <= 0;
      rsp_valid_o <= 0; rsp_rdata_o <= 0;
      rsp_corrected_o <= 0; rsp_uncorrectable_o <= 0;
    end else begin
      if (init_done_o && state != ST_REFRESH)
        refresh_count <= refresh_count + 1'b1;
      if (rsp_valid_o && rsp_ready_i) rsp_valid_o <= 0;
      case (state)
        ST_WAIT: begin
          if (init_count + 1 >= INIT_WAIT_CYCLES) begin state <= ST_INIT_NOP; init_count <= 0; end
          else init_count <= init_count + 1'b1;
        end
        ST_INIT_NOP: state <= ST_INIT_PRE;
        ST_INIT_PRE: state <= ST_INIT_GAP1;
        ST_INIT_GAP1: state <= ST_INIT_REF1;
        ST_INIT_REF1: state <= ST_INIT_RFC1;
        ST_INIT_RFC1: state <= ST_INIT_REF2;
        ST_INIT_REF2: state <= ST_INIT_RFC2;
        ST_INIT_RFC2: state <= ST_INIT_MRS;
        ST_INIT_MRS: state <= ST_INIT_MRD;
        ST_INIT_MRD: begin state <= ST_READY; init_done_o <= 1; refresh_count <= 0; end
        ST_READY: begin
          if (refresh_count + 32 >= REFRESH_CYCLES) state <= ST_REFRESH;
          else if (req_valid_i && req_ready_o) begin
            addr_q <= req_addr_i; write_q <= req_write_i;
            wdata_q <= req_wdata_i; wstrb_q <= req_wstrb_i;
            write_mask_q <= {{8{req_wstrb_i[7]}},{8{req_wstrb_i[6]}},
              {8{req_wstrb_i[5]}},{8{req_wstrb_i[4]}},{8{req_wstrb_i[3]}},
              {8{req_wstrb_i[2]}},{8{req_wstrb_i[1]}},{8{req_wstrb_i[0]}}};
            beat_q <= 0;
            state <= ST_ADDR;
          end
        end
        ST_ADDR: begin
            physical_q <= physical_base;
            if (write_q && wstrb_q == 8'hff) begin
              encode_data_q <= wdata_q; access_read_q <= 0; state <= ST_ENCODE;
            end else begin
              codeword_q <= 0; access_read_q <= 1; state <= ST_ACT;
            end
        end
        ST_REFRESH: begin refresh_count <= 0; state <= ST_RFC1; end
        ST_RFC1: state <= ST_RFC2;
        ST_RFC2: state <= ST_READY;
        ST_ACT: state <= ST_RCD;
        ST_RCD: state <= ST_ACCESS;
        ST_ACCESS: begin
          if (access_read_q) state <= ST_RD_WAIT1;
          else state <= ST_WR_GAP1;
        end
        ST_RD_WAIT1: state <= ST_RD_WAIT2;
        ST_RD_WAIT2: begin
          codeword_q <= assembled;
          if (beat_q != 2) begin
            beat_q <= beat_q + 1'b1;
            physical_q <= physical_q + 1'b1;
            state <= ST_ACT;
          end
          else state <= ST_ECC_SYNDROME;
        end
        ST_ECC_SYNDROME: begin
          syndrome_q <= assembled_syndrome; overall_q <= ^codeword_q;
          state <= ST_ECC_DECODE;
        end
        ST_ECC_DECODE: begin decoded_q <= decoded_data; state <= ST_ECC_DECIDE; end
        ST_ECC_DECIDE: begin
          if (!write_q) begin
            rsp_rdata_o <= decoded_q;
            rsp_corrected_o <= overall_q;
            rsp_uncorrectable_o <= (syndrome_q != 0) && !overall_q;
            rsp_valid_o <= 1; state <= ST_RESP;
          end else if ((syndrome_q != 0) && !overall_q) begin
            rsp_rdata_o <= decoded_q; rsp_corrected_o <= 0;
            rsp_uncorrectable_o <= 1; rsp_valid_o <= 1; state <= ST_RESP;
          end else begin
            encode_data_q <= merged_data; state <= ST_ENCODE;
          end
        end
        ST_ENCODE: begin
          hamming_q <= placed_data; state <= ST_ENCODE_PARTS;
        end
        ST_ENCODE_PARTS: begin
          encode_part0_q <= encode_part0; encode_part1_q <= encode_part1;
          encode_part2_q <= encode_part2; encode_part3_q <= encode_part3;
          encode_overall_parts_q <= {^hamming_q[70:54],^hamming_q[53:36],^hamming_q[35:18],^hamming_q[17:0]};
          state <= ST_ENCODE_COMBINE;
        end
        ST_ENCODE_COMBINE: begin
          encode_parity_q <= encode_part0_q ^ encode_part1_q ^ encode_part2_q ^ encode_part3_q;
          encode_data_overall_q <= ^encode_overall_parts_q;
          state <= ST_ENCODE_FINISH;
        end
        ST_ENCODE_FINISH: begin
          codeword_q <= encoded_word; access_read_q <= 0; beat_q <= 0;
          physical_q <= physical_base;
          state <= ST_ACT;
        end
        ST_WR_GAP1: state <= ST_WR_GAP2;
        ST_WR_GAP2: begin
          if (beat_q != 2) begin
            beat_q <= beat_q + 1'b1;
            physical_q <= physical_q + 1'b1;
            state <= ST_ACT;
          end
          else begin
            rsp_rdata_o <= 0; rsp_corrected_o <= 0; rsp_uncorrectable_o <= 0;
            rsp_valid_o <= 1; state <= ST_RESP;
          end
        end
        ST_RESP: if (rsp_valid_o && rsp_ready_i) state <= ST_READY;
        default: state <= ST_WAIT;
      endcase
    end
  end
endmodule
