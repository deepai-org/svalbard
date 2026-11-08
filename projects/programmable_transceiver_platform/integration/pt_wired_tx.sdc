# Wired TX word interface: pt_digital wire_tx_data -> pt_analog_physical serializer parallel
# load (consolidation P2-6; integration/macro-contract.md "Wired word width").
#
# Assumption, to be confirmed by the wired_tx serializer owner:
#   * the serializer loads the 10-bit word on the FALLING edge of the word clock
#     (wire_tx_clk), half a word period after pt_digital launches it on the rising edge
#     (the capture scheme documented for the former pt_wtx_pattern);
#   * load-register setup 0.5 ns and hold 0.3 ns at that falling edge;
#   * wire_tx_clk reaches pt_digital's launch flops and the serializer load with equal
#     latency (ideal clocks here; replace with the clock-tree insertion delays once known).
# Budget therefore: clock-to-output + any output mux + wiring <= T_word/2 - 0.5 ns
# (3.5 ns at the 125 MHz word clock of 2.5 Gb/s). Rising-edge capture would double it.
#
# Variables (set before sourcing): wtx_clk = clock name, wtx_data = output port pattern.
if {![info exists wtx_clk]}  { set wtx_clk wire_tx_clk }
if {![info exists wtx_data]} { set wtx_data {wire_tx_data*} }
set wtx_setup_ns 0.5
set wtx_hold_ns  0.3
set_output_delay -clock $wtx_clk -clock_fall -max $wtx_setup_ns [get_ports $wtx_data]
set_output_delay -clock $wtx_clk -clock_fall -min [expr {-$wtx_hold_ns}] [get_ports $wtx_data]
