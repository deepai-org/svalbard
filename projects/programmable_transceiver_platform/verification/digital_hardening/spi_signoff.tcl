# SPI-only (SCLK domain) STA of pt_digital_macro with a model of the top-level SCLK/MOSI/CS_N/MISO routes
# and the provider pad cells (integration-plan G6). Driven by spi_signoff.py, which computes the numbers
# passed in through the environment. All times are referenced to the SCLK edge AT THE MACRO PIN.
#   ODB | (NL + SPEF)   placed/CTS database (placement-estimated RC) or routed netlist + SPEF
#   SCLIB               standard-cell Liberty of this corner;  SDC  macro SDC;  P  SCLK period (ns)
#   IN_MAX / IN_MIN     MOSI, CS_N arrival after the SCLK FALL at the macro pin (host tco + pad/route skew)
#   OUT_MAX / OUT_MIN   MISO external delay to the host's sampling RISE (route + pad + host budget + SCLK-in delay)
#   DE / DL             early / late timing derate (on-chip variation), optional
#   TR_MIN / TR_MAX     input transition at the macro pins;  CL  load on spi_miso / spi_miso_oe (pF)
proc e {n} { return $::env($n) }
read_liberty [e SCLIB]
if {[info exists ::env(ODB)]} {
    read_lef /pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/techlef/gf180mcu_fd_sc_mcu7t5v0__[e TLEF].tlef
    read_lef /pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lef/gf180mcu_fd_sc_mcu7t5v0.lef
    read_db [e ODB]
} else {
    read_verilog [e NL]; link_design pt_digital_macro; read_spef [e SPEF]
}
set SCLK_PERIOD [e P]
set PT_LIB_CHARACTERIZED 1; set HOST_RATE_DIV 1; set PT_ODDR_CHECKS 0
source [e SDC]
set_propagated_clock [all_clocks]
if {[info exists ::env(ODB)]} {
    # LibreLane's layer RC of this flow (OpenROAD.DumpRCValues), scaled by RCSCALE for the two-sided bound
    set k [e RCSCALE]
    foreach {l r c} {Metal2 0.000385861 0.000135357 Metal3 0.000206673 0.000146141 Metal4 0.000168609 0.000150688 Metal5 0.0000792778 0.000155595} {
        set_layer_rc -layer $l -resistance [expr {$r * $k}] -capacitance [expr {$c * $k}]
    }
    set_wire_rc -signal -layers {Metal2 Metal3 Metal4}
    set_wire_rc -clock -layers {Metal2 Metal3 Metal4}
    estimate_parasitics -placement
}
# On-chip variation: early/late derate of every cell and net delay (clock and data), CRPR on. DE/DL from the driver.
if {[info exists ::env(DE)]} { set_timing_derate -early [e DE]; set_timing_derate -late [e DL] }
set spi_in [get_ports {spi_mosi spi_cs_n}]
set spi_out [get_ports {spi_miso spi_miso_oe}]
set_input_delay -max [e IN_MAX] -clock sclk -clock_fall $spi_in
set_input_delay -min [e IN_MIN] -clock sclk -clock_fall $spi_in
set_output_delay -max [e OUT_MAX] -clock sclk $spi_out
set_output_delay -min [e OUT_MIN] -clock sclk $spi_out
set_input_transition -max [e TR_MAX] [get_ports {spi_sclk spi_mosi spi_cs_n}]
set_input_transition -min [e TR_MIN] [get_ports {spi_sclk spi_mosi spi_cs_n}]
set_load [e CL] $spi_out
set sk {}
foreach c [all_clocks] { set n [get_name $c]; if {$n eq "sclk" || [string match *_sclk $n]} { lappend sk $c } }
puts "SPI_CLOCKS [lmap c $sk {get_name $c}]"
proc worst {dly args} {
    set ps [find_timing_paths -path_delay $dly -group_path_count 1 -sort_by_slack {*}$args]
    if {![llength $ps]} { return "none" }
    set p [lindex $ps 0]; set s [get_property $p slack]
    return "[format %.3f $s] [get_full_name [get_property $p startpoint]] -> [get_full_name [get_property $p endpoint]]"
}
foreach dly {max min} {
    puts "R $dly reg2reg  [worst $dly -from $sk -to $sk]"
    puts "R $dly in2reg   [worst $dly -from $spi_in -to $sk]"
    puts "R $dly miso     [worst $dly -to $spi_out]"
    puts "R $dly cfg_out  [worst $dly -from $sk -to [all_outputs]]"
    puts "R $dly to_sclk  [worst $dly -to $sk]"
    puts "R $dly from_sclk [worst $dly -from $sk]"
}
# SCLK insertion delay and the MISO launch path, for the report
report_checks -path_delay max -to [get_ports spi_miso] -format full_clock_expanded -fields {slew cap} -digits 3
report_checks -path_delay min -from $spi_in -to $sk -format full_clock_expanded -fields {slew cap} -digits 3
report_checks -path_delay max -from $sk -to $sk -format full_clock_expanded -digits 3
report_checks -path_delay min -from $sk -to $sk -format full_clock_expanded -digits 3
report_check_types -max_slew -violators
