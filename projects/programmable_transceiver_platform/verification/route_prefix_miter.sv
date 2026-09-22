module route_prefix_miter(input allow_payload,input[7:0]wire_slots,iq_slots,
 input[79:0]words,input[5:0]left_wire,left_iq,output mismatch);
 wire[79:0]aw,aq,bw,bq;wire[3:0]ac,ad,bc,bd;wire[5:0]an,am,bn,bm;
 pt_block_route_mask a(allow_payload,wire_slots,iq_slots,words,left_wire,left_iq,aw,aq,ac,ad,an,am);
 pt_block_route_prefix b(allow_payload,wire_slots,iq_slots,words,left_wire,left_iq,bw,bq,bc,bd,bn,bm);
 assign mismatch=({aw,aq,ac,ad,an,am}!={bw,bq,bc,bd,bn,bm});
endmodule
