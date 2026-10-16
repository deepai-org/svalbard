// Generic TX-pad configuration transaction. No protocol profiles.
// Inputs are synchronous to clk except rst_n/supply_ok (asynchronous disable).
// Their release must be synchronized by the integration reset controller.
// Counts require clock-period/physical-path budgeting; they are not nanoseconds.
module pt_tx_pad_sequence #(
    parameter integer PRE_CYCLES = 2,
    parameter integer POST_CYCLES = 2,
    parameter integer LOAD_CYCLES = 2
)(
    input wire clk, rst_n, supply_ok,
    input wire commit,
    input wire [4:0] request, // MAIN, POST, TMDS, DETECT, TERM
    input wire analog_ready, // qualified readiness; no ideal timer substitution
    output wire command_ready,
    output reg [4:0] active_request,
    output reg qualified, // analog path enabled; not payload readiness
    output reg traffic_ready,
    output reg buffer_request,
    output reg fault
);
    localparam integer BLANK_MAX = PRE_CYCLES > POST_CYCLES ? PRE_CYCLES : POST_CYCLES;
    localparam integer MAX_COUNT = BLANK_MAX > LOAD_CYCLES ? BLANK_MAX : LOAD_CYCLES;
    localparam integer CW = MAX_COUNT < 2 ? 1 : $clog2(MAX_COUNT+1);
    localparam [2:0] IDLE=0, PRE=1, POST=2, WAIT_READY=3, SETTLE=4;
    reg [2:0] state;
    reg [CW-1:0] left;
    reg [4:0] pending;
    wire reset_ok = rst_n && supply_ok;
    wire conflict = ((request[2] || request[3]) &&
                     (request[0] || request[1] || request[4])) ||
                    (request[2] && request[3]);
    assign command_ready = reset_ok && state == IDLE;
    initial begin
        if (PRE_CYCLES < 1 || POST_CYCLES < 1 || LOAD_CYCLES < 1) $fatal(1,"Blanking counts must be positive");
    end
    always @(posedge clk or negedge reset_ok) begin
        if (!reset_ok) begin
            state <= IDLE; left <= 0; pending <= 0;
            active_request <= 0; qualified <= 0; traffic_ready <= 0;
            buffer_request <= 0; fault <= 0;
        end else begin
            case (state)
                IDLE: begin
                    if (commit) begin
                        // Snapshot once; host changes while busy cannot leak through.
                        pending <= conflict ? 5'b0 : request;
                        fault <= conflict;
                        qualified <= 0; traffic_ready <= 0;
                        left <= PRE_CYCLES;
                        state <= PRE;
                    end else if (qualified && !analog_ready) begin
                        qualified <= 0; traffic_ready <= 0; fault <= 1;
                        pending <= 0; left <= PRE_CYCLES; state <= PRE;
                    end
                end
                PRE: begin
                    if (left > 1) left <= left - 1'b1;
                    else begin
                        active_request <= pending;
                        // Old termination has been disabled before buffer release.
                        // New buffer precharges independently of QUALIFIED.
                        buffer_request <= pending[4];
                        left <= POST_CYCLES; state <= POST;
                    end
                end
                POST: begin
                    if (left > 1) left <= left - 1'b1;
                    else if (active_request == 0 || fault) state <= IDLE;
                    else if (analog_ready) begin qualified <= 1; left <= LOAD_CYCLES; state <= SETTLE; end
                    else state <= WAIT_READY;
                end
                WAIT_READY: if (analog_ready) begin qualified <= 1; left <= LOAD_CYCLES; state <= SETTLE; end
                SETTLE: begin
                    // Keep the load applied while the buffer settles. A fresh
                    // contiguous run of good samples is required under load.
                    if (!analog_ready) left <= LOAD_CYCLES;
                    else if (left > 1) left <= left - 1'b1;
                    else begin traffic_ready <= 1; state <= IDLE; end
                end
                default: begin
                    state <= IDLE; qualified <= 0; traffic_ready <= 0; active_request <= 0;
                    buffer_request <= 0; fault <= 1;
                end
            endcase
        end
    end
endmodule
