module compact_rank_miter(input[79:0]words,input[7:0]selected,output mismatch);
 wire[79:0]a,b;wire[3:0]ac,bc;
 pt_lane_compact old(words,selected,a,ac);
 pt_lane_compact_rank candidate(words,selected,b,bc);
 assign mismatch=({a,ac}!={b,bc});
endmodule
