// Explicit one-hot lane selection by prefix rank; lane zero is earliest.
module pt_lane_compact_rank(input wire[79:0]words,input wire[7:0]selected,
 output wire[79:0]packed_words,output wire[3:0]word_count);
 function automatic[3:0]prefix(input[7:0]mask,input integer stop);
 integer k;begin prefix=0;for(k=0;k<8;k=k+1)if(k<stop)prefix=prefix+{3'b0,mask[k]};end
 endfunction
 assign word_count=prefix(selected,8);
 genvar dst,bitno,src;
 generate for(dst=0;dst<8;dst=dst+1)begin:destination
  wire[7:0]choose;
  for(src=0;src<8;src=src+1)begin:source
   assign choose[src]=selected[src]&&(prefix(selected,src)==dst);
  end
  for(bitno=0;bitno<10;bitno=bitno+1)begin:bit_mux
   wire[7:0]terms;
   for(src=0;src<8;src=src+1)begin:term
    assign terms[src]=choose[src]&&words[src*10+bitno];
   end
   assign packed_words[dst*10+bitno]=|terms;
  end
 end endgenerate
endmodule
