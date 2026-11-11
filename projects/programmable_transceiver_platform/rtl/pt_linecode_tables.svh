// 8b/10b code tables (IX-2 line-code offload), included inside pt_lc_rx / pt_lc_tx (rtl/pt_linecode.sv).
// Generated from verification/linecode_8b10b.py (D6, D4, A7, K28, K4); bit 0 = first on the line.
 function automatic [5:0] lc_e6(input [4:0] x, input k28, input rdn);  // 5b/6b, rdn = RD- before
  begin
   if (k28) lc_e6 = rdn ? 6'b111100 : 6'b000011;
   else case (x)
    5'd0: lc_e6 = rdn ? 6'b111001 : 6'b000110;
    5'd1: lc_e6 = rdn ? 6'b101110 : 6'b010001;
    5'd2: lc_e6 = rdn ? 6'b101101 : 6'b010010;
    5'd3: lc_e6 = rdn ? 6'b100011 : 6'b100011;
    5'd4: lc_e6 = rdn ? 6'b101011 : 6'b010100;
    5'd5: lc_e6 = rdn ? 6'b100101 : 6'b100101;
    5'd6: lc_e6 = rdn ? 6'b100110 : 6'b100110;
    5'd7: lc_e6 = rdn ? 6'b000111 : 6'b111000;
    5'd8: lc_e6 = rdn ? 6'b100111 : 6'b011000;
    5'd9: lc_e6 = rdn ? 6'b101001 : 6'b101001;
    5'd10: lc_e6 = rdn ? 6'b101010 : 6'b101010;
    5'd11: lc_e6 = rdn ? 6'b001011 : 6'b001011;
    5'd12: lc_e6 = rdn ? 6'b101100 : 6'b101100;
    5'd13: lc_e6 = rdn ? 6'b001101 : 6'b001101;
    5'd14: lc_e6 = rdn ? 6'b001110 : 6'b001110;
    5'd15: lc_e6 = rdn ? 6'b111010 : 6'b000101;
    5'd16: lc_e6 = rdn ? 6'b110110 : 6'b001001;
    5'd17: lc_e6 = rdn ? 6'b110001 : 6'b110001;
    5'd18: lc_e6 = rdn ? 6'b110010 : 6'b110010;
    5'd19: lc_e6 = rdn ? 6'b010011 : 6'b010011;
    5'd20: lc_e6 = rdn ? 6'b110100 : 6'b110100;
    5'd21: lc_e6 = rdn ? 6'b010101 : 6'b010101;
    5'd22: lc_e6 = rdn ? 6'b010110 : 6'b010110;
    5'd23: lc_e6 = rdn ? 6'b010111 : 6'b101000;
    5'd24: lc_e6 = rdn ? 6'b110011 : 6'b001100;
    5'd25: lc_e6 = rdn ? 6'b011001 : 6'b011001;
    5'd26: lc_e6 = rdn ? 6'b011010 : 6'b011010;
    5'd27: lc_e6 = rdn ? 6'b011011 : 6'b100100;
    5'd28: lc_e6 = rdn ? 6'b011100 : 6'b011100;
    5'd29: lc_e6 = rdn ? 6'b011101 : 6'b100010;
    5'd30: lc_e6 = rdn ? 6'b011110 : 6'b100001;
    5'd31: lc_e6 = rdn ? 6'b110101 : 6'b001010;
   endcase
  end
 endfunction
 function automatic [3:0] lc_e4(input [2:0] y, input k28, input a7, input rdn);  // 3b/4b, rdn = RD- after the 6b block
  begin
   if (k28) case (y)
    3'd0: lc_e4 = rdn ? 4'b1101 : 4'b0010;
    3'd1: lc_e4 = rdn ? 4'b0110 : 4'b1001;
    3'd2: lc_e4 = rdn ? 4'b0101 : 4'b1010;
    3'd3: lc_e4 = rdn ? 4'b0011 : 4'b1100;
    3'd4: lc_e4 = rdn ? 4'b1011 : 4'b0100;
    3'd5: lc_e4 = rdn ? 4'b1010 : 4'b0101;
    3'd6: lc_e4 = rdn ? 4'b1001 : 4'b0110;
    3'd7: lc_e4 = rdn ? 4'b1110 : 4'b0001;
   endcase
   else if (a7) lc_e4 = rdn ? 4'b1110 : 4'b0001;
   else case (y)
    3'd0: lc_e4 = rdn ? 4'b1101 : 4'b0010;
    3'd1: lc_e4 = rdn ? 4'b1001 : 4'b1001;
    3'd2: lc_e4 = rdn ? 4'b1010 : 4'b1010;
    3'd3: lc_e4 = rdn ? 4'b0011 : 4'b1100;
    3'd4: lc_e4 = rdn ? 4'b1011 : 4'b0100;
    3'd5: lc_e4 = rdn ? 4'b0101 : 4'b0101;
    3'd6: lc_e4 = rdn ? 4'b0110 : 4'b0110;
    3'd7: lc_e4 = rdn ? 4'b0111 : 4'b1000;
   endcase
  end
 endfunction
 function automatic [5:0] lc_d6(input [5:0] c);  // {valid, EDCBA}
  begin case (c)
   6'b000101: lc_d6 = {1'b1, 5'd15};
   6'b000110: lc_d6 = {1'b1, 5'd0};
   6'b000111: lc_d6 = {1'b1, 5'd7};
   6'b001001: lc_d6 = {1'b1, 5'd16};
   6'b001010: lc_d6 = {1'b1, 5'd31};
   6'b001011: lc_d6 = {1'b1, 5'd11};
   6'b001100: lc_d6 = {1'b1, 5'd24};
   6'b001101: lc_d6 = {1'b1, 5'd13};
   6'b001110: lc_d6 = {1'b1, 5'd14};
   6'b010001: lc_d6 = {1'b1, 5'd1};
   6'b010010: lc_d6 = {1'b1, 5'd2};
   6'b010011: lc_d6 = {1'b1, 5'd19};
   6'b010100: lc_d6 = {1'b1, 5'd4};
   6'b010101: lc_d6 = {1'b1, 5'd21};
   6'b010110: lc_d6 = {1'b1, 5'd22};
   6'b010111: lc_d6 = {1'b1, 5'd23};
   6'b011000: lc_d6 = {1'b1, 5'd8};
   6'b011001: lc_d6 = {1'b1, 5'd25};
   6'b011010: lc_d6 = {1'b1, 5'd26};
   6'b011011: lc_d6 = {1'b1, 5'd27};
   6'b011100: lc_d6 = {1'b1, 5'd28};
   6'b011101: lc_d6 = {1'b1, 5'd29};
   6'b011110: lc_d6 = {1'b1, 5'd30};
   6'b100001: lc_d6 = {1'b1, 5'd30};
   6'b100010: lc_d6 = {1'b1, 5'd29};
   6'b100011: lc_d6 = {1'b1, 5'd3};
   6'b100100: lc_d6 = {1'b1, 5'd27};
   6'b100101: lc_d6 = {1'b1, 5'd5};
   6'b100110: lc_d6 = {1'b1, 5'd6};
   6'b100111: lc_d6 = {1'b1, 5'd8};
   6'b101000: lc_d6 = {1'b1, 5'd23};
   6'b101001: lc_d6 = {1'b1, 5'd9};
   6'b101010: lc_d6 = {1'b1, 5'd10};
   6'b101011: lc_d6 = {1'b1, 5'd4};
   6'b101100: lc_d6 = {1'b1, 5'd12};
   6'b101101: lc_d6 = {1'b1, 5'd2};
   6'b101110: lc_d6 = {1'b1, 5'd1};
   6'b110001: lc_d6 = {1'b1, 5'd17};
   6'b110010: lc_d6 = {1'b1, 5'd18};
   6'b110011: lc_d6 = {1'b1, 5'd24};
   6'b110100: lc_d6 = {1'b1, 5'd20};
   6'b110101: lc_d6 = {1'b1, 5'd31};
   6'b110110: lc_d6 = {1'b1, 5'd16};
   6'b111000: lc_d6 = {1'b1, 5'd7};
   6'b111001: lc_d6 = {1'b1, 5'd0};
   6'b111010: lc_d6 = {1'b1, 5'd15};
   default: lc_d6 = 6'd0;
  endcase end
 endfunction
 function automatic [3:0] lc_d4(input [3:0] c);  // {valid, HGF}
  begin case (c)
   4'b0001: lc_d4 = {1'b1, 3'd7};
   4'b0010: lc_d4 = {1'b1, 3'd0};
   4'b0011: lc_d4 = {1'b1, 3'd3};
   4'b0100: lc_d4 = {1'b1, 3'd4};
   4'b0101: lc_d4 = {1'b1, 3'd5};
   4'b0110: lc_d4 = {1'b1, 3'd6};
   4'b0111: lc_d4 = {1'b1, 3'd7};
   4'b1000: lc_d4 = {1'b1, 3'd7};
   4'b1001: lc_d4 = {1'b1, 3'd1};
   4'b1010: lc_d4 = {1'b1, 3'd2};
   4'b1011: lc_d4 = {1'b1, 3'd4};
   4'b1100: lc_d4 = {1'b1, 3'd3};
   4'b1101: lc_d4 = {1'b1, 3'd0};
   4'b1110: lc_d4 = {1'b1, 3'd7};
   default: lc_d4 = 4'd0;
  endcase end
 endfunction
 function automatic [3:0] lc_dk4(input [3:0] c);  // K28 3b/4b after RD+ (001111): {valid, y}
  begin case (c)
   4'b0100: lc_dk4 = {1'b1, 3'd4};
   4'b1100: lc_dk4 = {1'b1, 3'd3};
   4'b0010: lc_dk4 = {1'b1, 3'd0};
   4'b1010: lc_dk4 = {1'b1, 3'd2};
   4'b0110: lc_dk4 = {1'b1, 3'd6};
   4'b0001: lc_dk4 = {1'b1, 3'd7};
   4'b1001: lc_dk4 = {1'b1, 3'd1};
   4'b0101: lc_dk4 = {1'b1, 3'd5};
   default: lc_dk4 = 4'd0;
  endcase end
 endfunction
