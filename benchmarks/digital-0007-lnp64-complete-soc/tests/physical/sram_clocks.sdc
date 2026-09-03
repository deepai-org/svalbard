# Applied after logical SRAM wrappers are replaced by the physical hierarchy.
set lnp64_sram_leaf_clocks [get_pins -hierarchical *leaf/CLK]
if {[llength $lnp64_sram_leaf_clocks] == 0} {
  error "no GF180 SRAM leaf clocks found"
}
create_generated_clock -name sram_clk -source [get_ports clk_200_i] \
  -divide_by 4 $lnp64_sram_leaf_clocks
set_clock_uncertainty 0.150 [get_clocks sram_clk]
