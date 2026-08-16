module counter (
    input  logic       clk,
    input  logic       rst,
    output logic [3:0] count
);
    always_ff @(posedge clk) begin
        if (rst) begin
            count <= 4'h0;
        end else begin
            count <= count + 4'h1;
        end
    end

`ifdef FORMAL
    logic f_past_valid = 1'b0;

    always_ff @(posedge clk) begin
        f_past_valid <= 1'b1;
        if (!f_past_valid) begin
            assume (rst);
        end else begin
            if ($past(rst)) begin
                assert (count == 4'h0);
            end else begin
                assert (count == $past(count) + 4'h1);
            end
        end
        cover (f_past_valid && !$past(rst) && count == 4'hf);
    end
`endif
endmodule
