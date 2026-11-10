# Timing constraints for the hardened core digital macro pt_digital_macro
# (rtl/pt_digital_macro.sv; flow verification/run_digital_hardening.sh).
#
# Clock targets (ns). Override any period by setting the Tcl variable before sourcing
# (verification/digital_hardening/sta_signoff.tcl re-sources this file at other rates).
#   sclk      SPI SCLK. Bench uses 10 MHz; spec starts at <=1 MHz. Constrained at 20 MHz.
#   ref       reference into the calibrator (REF_IN after the clocktree; the calibrator is a
#             slow SAR, any slower reference is fine). 100 MHz.
#   hword     core host word clock (clocktree host clock: line-divided or host_follow), one
#             10-bit word per edge in each direction. Spec top profile 312.5 MHz (156.25 MHz
#             DDR pins); the hardening target is set by HWORD_PERIOD (see evidence for fmax).
#   h2d       forwarded H2D_CLK pin clock: DDR = hword/2, SDR = hword. Constrained as DDR.
#   wtx/wrx   wired 20-bit double-word clocks (P3-6): <= 125 MHz (2.5 Gb/s at 4 bits per ring cycle).
#   rftx/rfrx RF sample clocks: 50 MHz (covers the 40 MS/s stretch profile).
#   ctw       pt_clocktree_slow word-divider clock (pt_prescale CK_OUT, <=156.25 MHz).
#   ctref     word reference into pt_clocktree_slow = ctw/10 (modulus 10).
#   ctdet     detector divider input clock (prescaled), 156.25 MHz.
#   fc0..fc5  frequency-counter sources (pt_freq_count, P3-7): ring FBCKs (VCO/16 <= ~69 MHz), ring_osc,
#             vco_replica, aosc (~35-56 MHz), LC prescale; all constrained at 156.25 MHz. They reach the
#             counters through a stopped-only select mux, so they are logically exclusive with each other.
foreach {v d} {SCLK_PERIOD 50.0 REF_PERIOD 10.0 HWORD_PERIOD 3.2 WTX_PERIOD 8.0 WRX_PERIOD 8.0
               RFTX_PERIOD 20.0 RFRX_PERIOD 20.0 CTW_PERIOD 6.4 CTDET_PERIOD 6.4 FC_PERIOD 6.4} {
    if {![info exists $v]} { set $v $d }
}
# HOST_RATE_DIV: reduced-rate fallback mode (see hcore below); the forwarded H2D clock follows it.
if {![info exists HOST_RATE_DIV]} {
    set HOST_RATE_DIV 1
    if {[info exists ::env(PT_HOST_RATE_DIV)]} { set HOST_RATE_DIV $::env(PT_HOST_RATE_DIV) }
}
if {[lsearch -exact {1 2 4} $HOST_RATE_DIV] < 0} {error "HOST_RATE_DIV must be 1, 2 or 4"}
set HCORE_PERIOD [expr {$HOST_RATE_DIV * $HWORD_PERIOD}]
if {![info exists H2D_PERIOD]}   { set H2D_PERIOD [expr {2.0 * $HCORE_PERIOD}] }
if {![info exists CTREF_PERIOD]} { set CTREF_PERIOD [expr {10.0 * $CTW_PERIOD}] }

# This custom SDC replaces the flow's base.sdc. Apply electrical limits here
# as well as in the flow configuration so repair sees the intended load/slew
# limits. Standalone STA uses the same defaults; flow overrides remain explicit.
foreach {constraint_variable constraint_command constraint_default} {
    MAX_TRANSITION_CONSTRAINT set_max_transition 1.0
    MAX_CAPACITANCE_CONSTRAINT set_max_capacitance 0.1
    MAX_FANOUT_CONSTRAINT set_max_fanout 12
} {
    set constraint_value $constraint_default
    if {[info exists ::env($constraint_variable)]} {
        set constraint_value $::env($constraint_variable)
    }
    $constraint_command $constraint_value [current_design]
}

create_clock -name sclk  -period $SCLK_PERIOD  [get_ports spi_sclk]
create_clock -name ref   -period $REF_PERIOD   [get_ports ref_clk]
create_clock -name hword -period $HWORD_PERIOD [get_ports host_word_clk]
create_clock -name h2d   -period $H2D_PERIOD   [get_ports h2d_clk]
create_clock -name wtx   -period $WTX_PERIOD   [get_ports wire_tx_clk]
create_clock -name wrx   -period $WRX_PERIOD   [get_ports wire_rx_clk]
create_clock -name rftx  -period $RFTX_PERIOD  [get_ports rf_tx_clk]
create_clock -name rfrx  -period $RFRX_PERIOD  [get_ports rf_rx_clk]
create_clock -name ctw   -period $CTW_PERIOD   [get_ports ct_wclk]
create_clock -name ctref -period $CTREF_PERIOD [get_ports ct_ref_clk]
create_clock -name ctdet -period $CTDET_PERIOD [get_ports ct_det_clk_in]
# Reduced-rate fallback (debug.host_link.rate, rtl/pt_host_link.sv pt_host_rate_clock). The host
# link word side and the whole transport core run on hcore = hword / HOST_RATE_DIV, selected by
# two kept mux2 cells. Each setting is a separate STA mode: HOST_RATE_DIV 1 (reset, full rate),
# 2 or 4. The mux selects are case-analysed so exactly one source reaches hcore per mode.
set HCORE_CLK hword
set rate_mux [get_pins -quiet -hierarchical *host_rate.rate_clock_mux/Z]
if {[llength $rate_mux]} {
    if {[llength $rate_mux] != 1} {error "Expected one host rate clock mux"}
    set_case_analysis [expr {$HOST_RATE_DIV == 1 ? 0 : 1}] [get_pins -hierarchical *host_rate.rate_clock_mux/S]
    set_case_analysis [expr {$HOST_RATE_DIV == 4 ? 1 : 0}] [get_pins -hierarchical *host_rate.rate_slow_mux/S]
    create_generated_clock -name hcore -source [get_ports host_word_clk] -divide_by $HOST_RATE_DIV $rate_mux
    set HCORE_CLK hcore
}
# The paired core retains the fast word clock at the host boundary. Its
# engines and FIFO readers use real divide-by-two clocks. Flattening may
# merge the identical TX/RX dividers; define each retained source once.
set HOST_TX_CLK $HCORE_CLK
set HOST_RX_CLK $HCORE_CLK
set HOST_ENGINE_PERIOD $HCORE_PERIOD
set host_pair_clks {}
set pair_dividers [get_pins -quiet -hierarchical *paired_core.*_boundary.pair_clock_buffer/Z]
if {[llength $pair_dividers] > 2} {error "Unexpected paired clock divider count"}
foreach pin $pair_dividers {
    set name [get_full_name $pin]
    set cname [expr {[string match *tx_boundary* $name] ? "hpair_tx" : "hpair_rx"}]
    set pair_source [expr {$HCORE_CLK eq "hcore" ? $rate_mux : [get_ports host_word_clk]}]
    create_generated_clock -name $cname -source $pair_source -divide_by 2 $pin
    lappend host_pair_clks $cname
    if {$cname eq "hpair_tx"} {set HOST_TX_CLK $cname} else {set HOST_RX_CLK $cname}
}
if {[llength $host_pair_clks] == 1} {
    set HOST_TX_CLK [lindex $host_pair_clks 0]
    set HOST_RX_CLK $HOST_TX_CLK
}
if {[llength $host_pair_clks]} {
    set HOST_ENGINE_PERIOD [expr {2.0*$HCORE_PERIOD}]
    # This source register feeds the low-word and saved-high registers only
    # on the once-per-pair enable. Formal proof covers phase, stable source
    # window and both launch branches (pt_pair_word_boundary.sby).
    set pair_launch [get_cells -of_objects [get_pins -hierarchical *paired_core.tx_boundary.launch_pair*/Q]]
    if {[llength $pair_launch] != 20} {error "Expected twenty pair launch registers"}
    set_multicycle_path 2 -setup -end -from $pair_launch -to [get_clocks $HCORE_CLK]
    set_multicycle_path 1 -hold -end -from $pair_launch -to [get_clocks $HCORE_CLK]
}
# The egress bank is shared by stopped-only exclusive owners. Define clocks
# after its physical mux so only these local alternatives are exclusive;
# both primary wired/RF clocks may continue running elsewhere in the macro.
set egress_clks {}
set egress_mux [get_pins -quiet -hierarchical *paired_core.egress_clock_mux/Z]
if {[llength $egress_mux]} {
    if {[llength $egress_mux] != 1} {error "Expected one shared egress clock mux"}
    create_generated_clock -name egress_wtx -master_clock wtx -source [get_ports wire_tx_clk] -combinational $egress_mux
    create_generated_clock -name egress_rftx -master_clock rftx -source [get_ports rf_tx_clk] -combinational -add $egress_mux
    set egress_clks {egress_wtx egress_rftx}
    set_clock_groups -logically_exclusive -group egress_wtx -group egress_rftx
    # Inactive outputs and count/empty paths are gated by the same stopped
    # owner that selects the clock. Never cut primary wtx/rftx globally.
    set_false_path -from [get_clocks egress_wtx] -to [get_clocks rftx]
    set_false_path -from [get_clocks egress_rftx] -to [get_clocks wtx]
    set_false_path -from [get_clocks egress_wtx] -to [get_ports rf_tx_sample*]
    set_false_path -from [get_clocks egress_rftx] -to [get_ports wire_tx_data*]
}
set fc_clks {}
for {set i 0} {$i < 6} {incr i} {
    create_clock -name fc$i -period $FC_PERIOD [get_ports "fc_src\[$i\]"]
    lappend fc_clks fc$i
}
set_clock_groups -logically_exclusive -group fc0 -group fc1 -group fc2 -group fc3 -group fc4 -group fc5
set all_clk_names [concat {sclk ref hword h2d wtx wrx rftx rfrx ctw ctref ctdet} $fc_clks $host_pair_clks $egress_clks]
if {$HCORE_CLK eq "hcore"} { lappend all_clk_names hcore }

set_clock_uncertainty 0.25 [all_clocks]

# Operating envelope (scratch/reviews/MANDATE.md, spec/tapeout-plan.md): 22-32 C junction,
# 3.15-3.35 V. The PDK ships only tt_025C_3v30 inside that window; its ss/ff libraries are at
# -40/125 C and 3.0/3.6 V. In-window process corners are emulated on the tt library with a
# uniform derate (cell and wire, clock and data, early and late = one global corner, not OCV):
#   ss_window 1.54: ss_n40C_3v00/tt = 1.37, ss_125C_3v00/tt = 1.87 (inv/nand/aoi/xor/mux/dff
#                   cell_rise at mid-table), linear in T to 32 C = 1.59 at 3.0 V, then
#                   alpha-power (Vt 0.7 V, alpha 1.3) 3.0 -> 3.15 V = /1.035.
#   ff_window 0.71: ff_n40C_3v60/tt = 0.59, ff_125C_3v60/tt = 0.82, to 22 C = 0.68 at 3.6 V,
#                   3.6 -> 3.35 V = x1.05.
#   tt: no derate.
# PnR uses ss_window (setup limited); signoff STA runs all three (sta_signoff.py). Reset and
# lockup safety are logic properties (formal proofs), independent of this timing window.
if {![info exists PT_TIMING_CORNER]} {
    set PT_TIMING_CORNER ss_window
    if {[info exists ::env(PT_TIMING_CORNER)]} { set PT_TIMING_CORNER $::env(PT_TIMING_CORNER) }
}
set pt_envelope_derate [dict get {ss_window 1.54 tt 1.0 ff_window 0.71} $PT_TIMING_CORNER]
# Electrical (slew/cap/fanout) repair must see undrated library values: derated slews make
# repair_design chain repeaters without bound (801k buffers in run dh-x-v3).
if {[info exists ::env(STEP_ID)] && [string match *RepairDesign* $::env(STEP_ID)]} {
    set pt_envelope_derate 1.0
}
if {$pt_envelope_derate != 1.0} {
    set_timing_derate -early $pt_envelope_derate
    set_timing_derate -late $pt_envelope_derate
}
set_clock_transition 0.15 [all_clocks]

# ---------------------------------------------------------------------------------------
# Boundary. Analog-side synchronous data: 20 % of the period for the macro-external part on
# each side (LibreLane IO_DELAY_CONSTRAINT convention; to be replaced by the analog owners'
# numbers). Loads: 20 fF analog inputs, 0.07291 pF (LibreLane default) elsewhere.
proc pt_io {clk period ins outs} {
    if {[llength $ins]}  { set_input_delay  [expr {0.2 * $period}] -clock $clk [get_ports $ins] }
    if {[llength $outs]} { set_output_delay [expr {0.2 * $period}] -clock $clk [get_ports $outs] }
}
pt_io wrx  $WRX_PERIOD  {wire_rx_data* wire_rx_valid} {}
pt_io wtx  $WTX_PERIOD  {wire_tx_request} {wire_tx_valid wire_idle}
# wire_tx_data: serializer loads on the falling word-clock edge, setup 0.5 ns / hold 0.3 ns
# (same values as integration/pt_wired_tx.sdc, inlined so the file is self-contained).
set_output_delay -clock wtx -clock_fall -max 0.5 [get_ports {wire_tx_data*}]
set_output_delay -clock wtx -clock_fall -min -0.3 [get_ports {wire_tx_data*}]
pt_io rfrx $RFRX_PERIOD {rf_rx_sample* rf_rx_valid} {}
pt_io rftx $RFTX_PERIOD {rf_tx_request} {rf_tx_sample* rf_tx_valid rf_mute}
pt_io ref  $REF_PERIOD  {calibration_above_target} {calibration_trial* cdr_freq_locked}
pt_io ctref $CTREF_PERIOD {ct_marker} {ct_armed ct_marker_seen ct_launched ct_arm_fault}
pt_io ctw  $CTW_PERIOD  {} {ct_word_clk ct_word_load ct_ser_run ct_bit_phase ct_qualified}
pt_io ctdet $CTDET_PERIOD {} {ct_det_div* ct_det_clk}

# SPI (Mode 0). Host launches MOSI/CS_N on the falling edge; allow 10 ns host + board + pad.
# MISO launches on our falling edge; host samples on the next rising edge with 10 ns budget.
set_input_delay 10.0 -clock sclk -clock_fall [get_ports {spi_mosi spi_cs_n}]
set_output_delay 10.0 -clock sclk [get_ports {spi_miso spi_miso_oe}]
# CS_N only gates the MISO pad enable/level combinationally; the host asserts CS_N at least half an
# SCLK period before the first edge (SPI mode 0 tCSS), so CS_N -> MISO is not an SCLK-cycle path.
set_false_path -from [get_ports spi_cs_n] -to [get_ports {spi_miso spi_miso_oe}]
# For the same reason CS_N is static at every SCLK edge of a transaction (it frames the 32 clocks):
# its paths to register data pins are not single-cycle; its reset (recovery) paths stay timed.
# Limit this collection to reachable data endpoints. all_registers -data_pins
# also includes tied-constant D pins, which OpenSTA rejects as endpoints.
set cs_data_ends {}
foreach pin [get_fanout -from [get_ports spi_cs_n] -flat -endpoints_only] {
    if {[string match */D [get_full_name $pin]]} { lappend cs_data_ends $pin }
}
if {[llength $cs_data_ends]} {
    set_false_path -from [get_ports spi_cs_n] -to $cs_data_ends
}

# Register-file outputs to analog and pad controls are quasi-static configuration launched by
# SCLK: they must settle within one SCLK period of the committing edge (output budget 20 %).
pt_io sclk $SCLK_PERIOD {} {analog_cfg* debug_cfg* island_en* atb0_sw* atb1_sw* rx_en_* clk_obs_oe wclk_obs_oe
    dbg_obs0* dbg_obs1* wdbg_obs* commit_toggle enable mode8 rf_trim* wire_trim* clock_trim* d2h_oe d2h_pdrv* d2h_sl
    en_eff* island_off*}

# ---------------------------------------------------------------------------------------
# Host link pins. H2D: FPGA forwards a centre-aligned clock (data changes UI/2 from each clock
# edge, UI = H2D_PERIOD/2) with +/-0.4 ns FPGA + board skew. Pad receivers are identical cells
# on data and clock, so only the macro-internal skew is checked here; pad DCD is in evidence.
set h2d_ui [expr {$H2D_PERIOD / 2.0}]
set h2d_skew 0.4
set_input_delay -max [expr {$h2d_ui/2.0 + $h2d_skew}] -clock h2d [get_ports h2d_pin*]
set_input_delay -min [expr {$h2d_ui/2.0 - $h2d_skew}] -clock h2d [get_ports h2d_pin*]
set_input_delay -max [expr {$h2d_ui/2.0 + $h2d_skew}] -clock h2d -clock_fall -add_delay [get_ports h2d_pin*]
set_input_delay -min [expr {$h2d_ui/2.0 - $h2d_skew}] -clock h2d -clock_fall -add_delay [get_ports h2d_pin*]
# D2H: data from hword rising-edge flops, forwarded clock from the hword falling edge.
# Checked in sta_signoff.tcl as a skew window (arrival min/max of data vs clock pin);
# here only a launch-side budget so the resizer keeps the paths short.
set_output_delay [expr {0.2 * $HCORE_PERIOD}] -clock $HCORE_CLK [get_ports {d2h_pin*}]
# d2h_clk_pin is the forwarded clock itself (toggle flop on the falling edge, or the gated inverted
# word clock): no data constraint; its skew against d2h_pin is reported by sta_signoff.py.

# Static/asynchronous inputs: island_pgood, fault, analog_status, wire_analog_status,
# ct_pll_lock, reset_n_pad, por_n and the ct_cfg_* straps have no clock. Each is synchronized
# before any sequential use (pg1/f1, observation muxes are raw by design, lock_s, reset
# synchronizers in every FIFO and clocktree domain) and is left unconstrained here.

# ---------------------------------------------------------------------------------------
# Clock-domain crossings. Only crossings that end in a documented synchronizer are cut;
# everything else between unrelated clocks stays timed (and is reported) until classified.
proc pt_cells {pattern} { return [get_cells -quiet $pattern] }
# Bounded crossing (OpenSTA has no -datapath_only): max delay with clock latency ignored, and no
# hold relation between the asynchronous clocks.
proc pt_bound_xing {limit dir objs {todir ""} {toobjs ""}} {
    if {$todir eq ""} {
        set_max_delay $limit -ignore_clock_latency $dir $objs
        set_false_path -hold $dir $objs
    } else {
        set_max_delay $limit -ignore_clock_latency $dir $objs $todir $toobjs
        set_false_path -hold $dir $objs $todir $toobjs
    }
}
# 1. Two-flop synchronizers: first stage of pt_sync_bit / pt_sync_vec ("meta"),
#    pt_regfile status/capture/power-good/fault/island/pattern synchronizers,
#    pt_clocktree_slow ref_s/pend_s/lock_s/arm_s/qual_s/den_s first stages.
set sync_first [concat \
    [pt_cells {*.meta*}] \
    [pt_cells {*regs.s1*}] [pt_cells {*regs.c1*}] [pt_cells {*regs.pg1*}] [pt_cells {*regs.on1*}] \
    [pt_cells {*regs.f1*}] [pt_cells {*regs.st1_*}] \
    [pt_cells {*clocktree.ref_s*}] [pt_cells {*clocktree.pend_s*}] [pt_cells {*clocktree.lock_s*}] \
    [pt_cells {*clocktree.arm_s*}] [pt_cells {*clocktree.qual_s*}] [pt_cells {*clocktree.den_s*}]]
if {[llength $sync_first]} { set_false_path -to $sync_first }
# 1b. Reset synchronizers (pt_async_fifo wr_reset/rd_reset, pt_enable_release release_state,
#     pt_pair_word_boundary reset_release, pt_host_link hrs/wrs). Their asynchronous reset is
#     driven from other domains (ENABLE release, rate-switch hold, rst_n); assertion is
#     asynchronous by design and release is re-timed by the two-flop chain itself. Only the
#     async RN/SN pins of these flops are cut; their D paths stay timed in their own domain.
set rst_sync_pins {}
foreach pat {*.wr_reset* *.rd_reset* *.wr_active* *.rd_active* *.release_state* *.e?.active* *.reset_release* *_boundary.local_rst* host.hrs* host.wrs*} {
    foreach c [pt_cells $pat] {
        foreach pin [get_pins -quiet -of_objects $c -filter "direction == input"] {
            if {[lsearch -exact {RN SETN SN} [get_property $pin lib_pin_name]] >= 0} { lappend rst_sync_pins $pin }
        }
    }
}
if {[llength $rst_sync_pins]} { set_false_path -to $rst_sync_pins }
# 1c. Rate-switch hold (pt_host_rate_clock hold_n, hword domain) asynchronously resets the host
#     link and transport core in every domain. Changes are stopped-only (ENABLE=0): wire/RF
#     domain flops are additionally held by their synchronized ENABLE (pt_sync_bit e2..e5,
#     f0..f3), so release into those domains is not a timed event. Release into the
#     hword/hcore/paired-clock family stays timed (recovery/removal).
set hold_src [pt_cells *host_rate.hold_n*]
if {[llength $hold_src]} {
    foreach c [all_clocks] {
        if {[lsearch -exact [concat hword hcore $host_pair_clks] [get_name $c]] < 0} {
            set_false_path -from $hold_src -to $c
        }
    }
}
# 2. Gray-coded async FIFO pointers (pt_async_fifo rg1 / wg1): bounded to the faster of the two
#    clock periods, so the pointer bits arrive within one sampling period.
#    Only data paths launched by the other side's clock are bounded (the reset-release recovery
#    paths into the same flops stay single-cycle in their own domain).
set clock_periods [dict create hword $HWORD_PERIOD hcore $HCORE_PERIOD h2d $H2D_PERIOD wtx $WTX_PERIOD wrx $WRX_PERIOD \
                              rftx $RFTX_PERIOD rfrx $RFRX_PERIOD]
foreach c $host_pair_clks {dict set clock_periods $c $HOST_ENGINE_PERIOD}
foreach {f wr rd} [list *.wire_in wrx $HOST_TX_CLK *.rf_in rfrx $HOST_TX_CLK \
                        *.wire_out $HOST_RX_CLK wtx *.rf_out $HOST_RX_CLK rftx *h2d_fifo h2d $HCORE_CLK] {
    set lim [expr {min([dict get $clock_periods $wr], [dict get $clock_periods $rd])}]
    set r1 [pt_cells "${f}.rg1*"]
    if {[llength $r1]} { pt_bound_xing $lim -from [get_clocks $rd] -to $r1 }
    set w1 [pt_cells "${f}.wg1*"]
    if {[llength $w1]} { pt_bound_xing $lim -from [get_clocks $wr] -to $w1 }
}
# 3. FIFO storage read across domains (dout = mem[rb]): a word is written at least two
#    reader-domain cycles before its Gray pointer can be seen; bounded to one reader period.
foreach {f rdper rdclk} [list *.wire_in $HOST_ENGINE_PERIOD $HOST_TX_CLK *.rf_in $HOST_ENGINE_PERIOD $HOST_TX_CLK *.wire_out $WTX_PERIOD wtx \
                        *.rf_out $RFTX_PERIOD rftx *h2d_fifo $HCORE_PERIOD $HCORE_CLK] {
    set m [pt_cells "${f}.mem*"]
    if {[llength $m]} { pt_bound_xing $rdper -from $m -to [get_clocks $rdclk] }
}
# Shared egress: the write side stays in the paired RX clock, while the
# read side uses one of the two generated mux clocks. Bound every Gray
# crossing and storage path for each selected mode.
foreach {rd per} [list egress_wtx $WTX_PERIOD egress_rftx $RFTX_PERIOD] {
    if {[lsearch -exact $egress_clks $rd] < 0} {continue}
    set lim [expr {min($HOST_ENGINE_PERIOD,$per)}]
    set r1 [pt_cells {*.egress.rg1*}]
    set w1 [pt_cells {*.egress.wg1*}]
    if {[llength $r1]} {pt_bound_xing $lim -from [get_clocks $rd] -to $r1}
    if {[llength $w1]} {pt_bound_xing $lim -from [get_clocks $HOST_RX_CLK] -to $w1}
    set m [pt_cells {*.egress.mem*}]
    if {[llength $m]} {pt_bound_xing $per -from $m -to [get_clocks $rd]}
}
# 4. pt_memory banks: playback written on SCLK only while disarmed and read on rf_tx after the
#    synchronized `loaded`/play_en; capture written on rf_rx and read over SPI only after the
#    synchronized capture_done (regfile c1/c2). Protocol-protected; bounded to the reader period.
set pb [pt_cells {*memory.playback*}]
if {[llength $pb]} { pt_bound_xing $RFTX_PERIOD -from $pb -to [get_clocks rftx] }
set cb [pt_cells {*memory.capture\[*}]
if {[llength $cb]} { pt_bound_xing $SCLK_PERIOD -from $cb -to [get_clocks sclk] }
set cd [pt_cells {digital.capture_done*}]
if {[llength $cd]} { pt_bound_xing $SCLK_PERIOD -from $cd -to [get_clocks sclk] }
# 4b. pt_freq_count (fca, fcb): Gray-coded source count into the reference domain (bounded like FIFO
#     pointers); handshake-held {count, lost, locked, diff} into SCLK (held stable while req != ack).
foreach inst {fca fcb} {
    set g [pt_cells "*${inst}.g1*"]
    if {[llength $g]} { pt_bound_xing $REF_PERIOD -from [get_clocks $fc_clks] -to $g }
    set h [pt_cells "*${inst}.hold*"]
    if {[llength $h]} { pt_bound_xing $SCLK_PERIOD -from $h -to [get_clocks sclk] }
}
# 4c. DBG_OBS0/1 and WDBG_OBS are raw, unsynchronized observation muxes of status from every
#     domain (spec/register-map.md, debug-controls obs_status). Only the SCLK-launched select is timed.
foreach c [lrange $all_clk_names 1 end] {
    set_false_path -from [get_clocks $c] -to [get_ports {dbg_obs0 dbg_obs1 wdbg_obs}]
}
# 4d. Pattern cores: since P3-6 the 20-bit generator/checker run directly on the 20-bit double-word
#     clocks (no clock gate): single-cycle paths, no multicycle exception.
# 5. Quasi-static SCLK configuration into the datapath clocks. Formal property P5 of the
#    register file (evidence/regfile-verification.json): non-live fields never change while
#    ENABLE=1, and every datapath is held in reset by its synchronized enable while ENABLE=0.
#    Live fields (pattern inject / check_clear, enable itself, host link mode, d2h_enable,
#    calibration start) enter other domains only through the pt_sync_* first stages above.
foreach c [lrange $all_clk_names 1 end] {
    set_false_path -from [get_clocks sclk] -to [get_clocks $c]
}

# OpenROAD CTS cannot build two trees for clocks on the same physical mux
# output. Build that shared tree once, using its faster (8 ns wired) mode.
# LibreLane re-reads PNR_SDC_FILE for each subsequent step, restoring BOTH
# alternatives for repair and STA; standalone/signoff STA also keeps both.
if {[info exists ::env(STEP_ID)] && $::env(STEP_ID) eq "OpenROAD.CTS" && [llength $egress_clks]} {
    delete_clock [get_clocks egress_rftx]
    puts "PT_CTS_SHARED_EGRESS: building one physical tree; dual-mode STA resumes after CTS"
}
