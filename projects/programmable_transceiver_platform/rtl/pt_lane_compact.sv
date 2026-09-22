// Candidate eight-word compactor. Lane zero is the earliest stream word.
// selected must already include metadata validity and remaining-count clipping.
module pt_lane_compact(input wire[79:0] words,input wire[7:0] selected,
 output reg[79:0] packed_words,output reg[3:0] word_count);
 integer lane;
 always @* begin
  packed_words=80'd0;
  word_count=4'd0;
  for(lane=0;lane<8;lane=lane+1)begin
   if(selected[lane])begin
    packed_words[word_count*10 +: 10]=words[lane*10 +: 10];
    word_count=word_count+1'b1;
   end
  end
 end
endmodule
