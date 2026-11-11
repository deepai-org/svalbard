# Timing constraints for the hardened core digital macro pt_digital_macro
# (rtl/pt_digital_macro.sv; flow verification/run_digital_hardening.sh).
#
# Clock targets (ns). Override any period by setting the Tcl variable before sourcing
# (verification/digital_hardening/sta_signoff.tcl re-sources this file at other rates).
#   sclk      SPI SCLK. Bench uses 10 MHz; spec starts at <=1 MHz. Constrained at 10 MHz (2026-11-11; was
#             20 MHz with no spec basis): Mode 0 makes the register-file write (data validation on the
#             last data bit) and the read response a HALF-period path; post-route ss_032C_3v15 needs
#             ~36 ns for the write validation, which 20 MHz (25 ns) cannot give. The address/command
#             decode is multicycle (pt_spi cmd_r/rd_addr) and reads use registered candidates.
#   ref       reference into the calibrator (REF_IN after the clocktree; the calibrator is a
#             slow SAR, any slower reference is fine). 100 MHz.
#   hword     host DDR clock from the clocktree (transport rework 2026-11-10): line/16, or the fixed
#             156.25 MHz host option (IX-2); one 10-bit word per pin per EDGE (312.5 Mword/s). No
#             macro logic runs at the 312.5 MHz word rate (in-window ss Liberty: a reset flop alone
#             needs ~3 ns). hddr = hword after the reduced-rate select (pad-edge DDR launch and
#             gearboxes), hcore = hddr/2 (78.125 MHz: the whole 40-bit transport core).
#   h2d       forwarded H2D_CLK pin clock: DDR = hddr rate (one word per edge), SDR = 2 x hddr
#             (reduced rates only). Constrained as DDR.
#   wtx/wrx   wired 40-bit quad clocks (AC-1 S3): pt_wiredtx WORD_CLK40 / pt_wrx_cap WCLK40,
#             line/40: 62.5 MHz at 2.5 Gb/s, constrained at 12.3 ns = 3.24 Gb/s (IX-1 continuous
#             range top; IX-2 3.0/3.125 Gb/s with the 8b/10b offload).
#   rftx/rfrx RF sample clocks: 50 MHz (covers the 40 MS/s stretch profile).
#   ctw       pt_clocktree_slow word-divider clock (pt_prescale CK_OUT, <=156.25 MHz).
#   ctref     word reference into pt_clocktree_slow = ctw/10 (modulus 10).
#   ctdet     detector divider input clock (prescaled), 156.25 MHz.
#   fc0..fc5  frequency-counter sources (pt_freq_count, P3-7): ring FBCKs (VCO/16 <= ~69 MHz), ring_osc,
#             vco_replica, aosc (~35-56 MHz), LC prescale; all constrained at 156.25 MHz. They reach the
#             counters through a stopped-only select mux, so they are logically exclusive with each other.
foreach {v d} {SCLK_PERIOD 100.0 REF_PERIOD 10.0 HWORD_PERIOD 6.4 WTX_PERIOD 12.3 WRX_PERIOD 12.3
               RFTX_PERIOD 20.0 RFRX_PERIOD 20.0 CTW_PERIOD 6.4 CTDET_PERIOD 6.4 FC_PERIOD 6.4} {
    if {![info exists $v]} { set $v $d }
}
# HOST_RATE_DIV: reduced-rate fallback mode (see hddr below); the forwarded H2D clock follows it.
if {![info exists HOST_RATE_DIV]} {
    set HOST_RATE_DIV 1
    if {[info exists ::env(PT_HOST_RATE_DIV)]} { set HOST_RATE_DIV $::env(PT_HOST_RATE_DIV) }
}
if {[lsearch -exact {1 2 4} $HOST_RATE_DIV] < 0} {error "HOST_RATE_DIV must be 1, 2 or 4"}
set HDDR_PERIOD [expr {$HOST_RATE_DIV * $HWORD_PERIOD}]
set HCORE_PERIOD [expr {2.0 * $HDDR_PERIOD}]
# HLINK_PERIOD: the word time (half a DDR period); kept as a variable for the reports only.
set HLINK_PERIOD [expr {$HDDR_PERIOD / 2.0}]
if {![info exists H2D_PERIOD]}   { set H2D_PERIOD $HDDR_PERIOD }
if {![info exists CTREF_PERIOD]} { set CTREF_PERIOD [expr {10.0 * $CTW_PERIOD}] }

# This custom SDC replaces the flow's base.sdc. Apply electrical limits here
# as well as in the flow configuration so repair sees the intended load/slew
# limits. Standalone STA uses the same defaults; flow overrides remain explicit.
# Limits are AT ss_032C_3v15 (the flow's repair corner since 2026-11-11). Measured on the AC-1 netlist
# (repair_design after global placement, 1716x1455): 1.0 ns -> +151 % cell area (120 % utilization,
# illegal), 1.8 ns -> +57 % (75 %), 2.0 ns -> +48 % (71 %), 2.5 ns / 0.2 pF -> +36 % (65 %). The
# electrical limit only bounds non-critical nets; critical paths are sized by repair_timing at ss.
# Run TC1 at 2.5 ns / 0.2 pF ended at ~71 % utilization and detailed routing stalled (31.7k DRCs after
# 8 iterations; AC1_R4 at 62 % reached 0 by iteration 6), so the limit is 3.0 ns / 0.25 pF (about the
# former tt 2.0 ns limit expressed at ss).
foreach {constraint_variable constraint_command constraint_default} {
    MAX_TRANSITION_CONSTRAINT set_max_transition 3.0
    MAX_CAPACITANCE_CONSTRAINT set_max_capacitance 0.25
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
# SP-03 TX interpolator mode (rtl/pt_interp2x.sv, digital.transport_config.tx_interp, stopped-only):
# PT_TX_INTERP 0 (bypass, reset): rf_tx_clk at RFTX_PERIOD clocks the core's RF TX side directly.
# PT_TX_INTERP 1 (halfband): rf_tx_clk is the 80 MHz DAC clock and the core RF TX side, playback
# memory and interpolator FIR run on rfhalf = rf_tx_clk / 2. Each setting is a separate STA mode.
if {![info exists PT_TX_INTERP]} {
    set PT_TX_INTERP 0
    if {[info exists ::env(PT_TX_INTERP)]} { set PT_TX_INTERP $::env(PT_TX_INTERP) }
}
if {$PT_TX_INTERP} { set RFTX_PERIOD 12.5 }
create_clock -name rftx  -period $RFTX_PERIOD  [get_ports rf_tx_clk]
set RF_CORE_MASTER rftx
set RF_CORE_SOURCE [get_ports rf_tx_clk]
set interp_mux [get_pins -quiet -hierarchical *interp.core_clock_mux.cell/S]
if {[llength $interp_mux]} {
    set_case_analysis [expr {$PT_TX_INTERP ? 1 : 0}] $interp_mux
    if {!$PT_TX_INTERP} {
        # bypass: the FIR registers are unused (samples pass combinationally); no timing on them
        set_false_path -to [get_cells -quiet -hierarchical {*interp.x* *interp.mid_q* *interp.lane* *interp.v* *interp.y* *interp.yv*}]
        # ... and nothing they launch is used: out_sample/out_valid = in_sample/in_valid (halfband = 0)
        set_false_path -from [get_cells -quiet -hierarchical {*interp.x* *interp.mid_q* *interp.lane* *interp.v* *interp.y* *interp.yv*}]
    }
    if {$PT_TX_INTERP} {
        set hb [get_pins -hierarchical *interp.half_clock_buf.cell/Z]
        create_generated_clock -name rfhalf -source [get_ports rf_tx_clk] -divide_by 2 $hb
        set RF_CORE_MASTER rfhalf
        set RF_CORE_SOURCE $hb
    }
}
create_clock -name rfrx  -period $RFRX_PERIOD  [get_ports rf_rx_clk]
create_clock -name ctw   -period $CTW_PERIOD   [get_ports ct_wclk]
create_clock -name ctref -period $CTREF_PERIOD [get_ports ct_ref_clk]
create_clock -name ctdet -period $CTDET_PERIOD [get_ports ct_det_clk_in]
# Reduced-rate fallback (debug.host_link.rate, rtl/pt_host_link.sv pt_host_rate_clock). The host
# link and the whole transport core run from hddr = hword / HOST_RATE_DIV, selected by two kept
# mux2 cells. Each setting is a separate STA mode: HOST_RATE_DIV 1 (reset, full rate), 2 or 4.
# The mux selects are case-analysed so exactly one source reaches hddr per mode.
set rate_mux [get_pins -quiet -hierarchical *host_rate.rate_clock_mux/Z]
if {[llength $rate_mux] != 1} {error "Expected one host rate clock mux"}
set_case_analysis [expr {$HOST_RATE_DIV == 1 ? 0 : 1}] [get_pins -hierarchical *host_rate.rate_clock_mux/S]
set_case_analysis [expr {$HOST_RATE_DIV == 4 ? 1 : 0}] [get_pins -hierarchical *host_rate.rate_slow_mux/S]
create_generated_clock -name hddr -source [get_ports host_word_clk] -divide_by $HOST_RATE_DIV $rate_mux
# SDR forwarded-clock word clock (2 x hddr; equals hword at full and div2 rate, hword/2 at div4).
set word_mux [get_pins -quiet -hierarchical *host_rate.word_clock_mux/Z]
if {[llength $word_mux] == 1} {
    set_case_analysis [expr {$HOST_RATE_DIV == 4 ? 1 : 0}] [get_pins -hierarchical *host_rate.word_clock_mux/S]
    create_generated_clock -name hsdr -source [get_ports host_word_clk] -divide_by [expr {$HOST_RATE_DIV == 4 ? 2 : 1}] $word_mux
}
# AC-1 core clock (rtl/pt_host_link.sv pt_host_divider): one hddr toggle flop behind a kept root
# buffer; every hcore edge coincides with a rising hddr edge, as the generated-clock waveform states.
set core_root [get_pins -quiet -hierarchical *host.divider.core_root*/Z]
if {[llength $core_root] != 1} {error "Expected one hcore divider root"}
create_generated_clock -name hcore -source $rate_mux -divide_by 2 $core_root
set host_clks {hddr hcore}
if {[llength [get_clocks -quiet hsdr]]} { lappend host_clks hsdr }
# D2H 4:1 gearbox: the hold register x (hddr) loads the hcore prefix register only on the hddr
# edges that coincide with hcore rising edges, i.e. two hddr periods after the prefix changed
# (proof: verification/formal/pt_d2h_gearbox_fv.sv, `make transceiver-pair-word-formal`).
set gearbox_regs [get_cells -of_objects [get_pins -hierarchical *host.gearbox.x*/Q]]
if {[llength $gearbox_regs] != 40} {error "Expected 40 D2H gearbox hold registers ([llength $gearbox_regs])"}
set_multicycle_path 2 -setup -end -from [get_clocks hcore] -to $gearbox_regs
set_multicycle_path 1 -hold -end -from [get_clocks hcore] -to $gearbox_regs
# D2H falling launch: q_f (hddr falling) takes x (held two periods) or f3 (held two periods), and the
# selected one is always 1.5 periods old (same proof, `ifdef FORMAL in pt_d2h_gearbox): the next
# falling edge but one is the capture edge.
set qf_regs [get_cells -of_objects [get_pins -hierarchical *host.gearbox.q_f*/Q]]
set x3_regs [concat $gearbox_regs [get_cells -of_objects [get_pins -hierarchical *host.gearbox.f3*/Q]]]
if {[llength $qf_regs] != 10} {error "Expected 10 D2H falling launch registers ([llength $qf_regs])"}
set_multicycle_path 2 -setup -end -from $x3_regs -to $qf_regs
set_multicycle_path 1 -hold -end -from $x3_regs -to $qf_regs
# H2D: the falling-word hold register fh is written into the quad FIFO memory on the rising edge
# 1.5 periods after it was written (proof: verification/formal/pt_h2d_gearbox_fv.sv).
set fh_regs [get_cells -of_objects [get_pins -hierarchical *host.h2d.fh*/Q]]
set h2d_mem [get_cells -of_objects [get_pins -hierarchical *host.h2d.mem*/Q]]
if {[llength $fh_regs] != 20} {error "Expected 20 H2D falling hold registers ([llength $fh_regs])"}
if {[llength $h2d_mem] != 320} {error "Expected 320 H2D quad FIFO bits ([llength $h2d_mem])"}
set_multicycle_path 2 -setup -end -from $fh_regs -to $h2d_mem
set_multicycle_path 1 -hold -end -from $fh_regs -to $h2d_mem
# Reset release into the host link's falling-edge flops (q_f, c_f, f, fh and the phase copies
# nsel) is a half-period recovery path that may resolve on either of two falling edges; the design
# is insensitive to which (all those flops and their sources are zero then; the D2H proof covers a
# one-edge-late release). Not timed.
set nrn {}
foreach c [get_cells -hierarchical -quiet -filter "ref_name =~ *__dffnrnq*"] {
    if {[string match *host.* [get_full_name $c]]} { lappend nrn [get_pins -of_objects $c -filter "lib_pin_name == RN"] }
}
if {[llength $nrn]} { set_false_path -to $nrn }
# Shared ingress bank (exclusive owners, like egress below): its write clock is the selected
# owner's input clock after one physical mux.
set ingress_clks {}
set ingress_mux [get_pins -quiet -hierarchical *core.ingress_clock_mux*/Z]
if {[llength $ingress_mux]} {
    if {[llength $ingress_mux] != 1} {error "Expected one shared ingress clock mux"}
    create_generated_clock -name ingress_wrx -master_clock wrx -source [get_ports wire_rx_clk] -combinational $ingress_mux
    create_generated_clock -name ingress_rfrx -master_clock rfrx -source [get_ports rf_rx_clk] -combinational -add $ingress_mux
    set ingress_clks {ingress_wrx ingress_rfrx}
    set_clock_groups -logically_exclusive -group ingress_wrx -group ingress_rfrx
    set_false_path -from [get_clocks rfrx] -to [get_clocks ingress_wrx]
    set_false_path -from [get_ports {wire_rx_data* wire_rx_valid}] -to [get_clocks ingress_rfrx]
}
# The egress bank is shared by stopped-only exclusive owners. Define clocks
# after its physical mux so only these local alternatives are exclusive;
# both primary wired/RF clocks may continue running elsewhere in the macro.
set egress_clks {}
set egress_mux [get_pins -quiet -hierarchical *core.egress_clock_mux*/Z]
if {[llength $egress_mux]} {
    if {[llength $egress_mux] != 1} {error "Expected one shared egress clock mux"}
    create_generated_clock -name egress_wtx -master_clock wtx -source [get_ports wire_tx_clk] -combinational $egress_mux
    create_generated_clock -name egress_rftx -master_clock $RF_CORE_MASTER -source $RF_CORE_SOURCE -combinational -add $egress_mux
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
# pt_freq_count block clocks (2026-11-10 timing rework): the Johnson counter MSB, through the kept
# buffer blk_clock_buf, is the source divided by 8 (50 % duty); it clocks the two Gray block counters
# (ha on its fall, hb on its rise). One generated clock per instance and per selectable source.
set fc_groups {}
for {set i 0} {$i < 6} {incr i} {
    set grp [list fc$i]
    foreach inst {fca fcb} {
        set b [get_pins -quiet -hierarchical "*${inst}.blk_clock_buf.cell/Z"]
        if {[llength $b] == 1} {
            create_generated_clock -name ${inst}_blk$i -master_clock fc$i -source [get_ports "fc_src\[$i\]"] \
                -divide_by 8 -add $b
            lappend grp ${inst}_blk$i
            lappend fc_clks ${inst}_blk$i
        }
    }
    lappend fc_groups -group $grp
}
set_clock_groups -logically_exclusive {*}$fc_groups
# MEMORY v3 (AC-1 sharing S1): the egress bank array is also the SPI playback memory. Its write
# clock is one stopped-only mux (core.egress.spi_port.memory_clock_mux): hcore while streaming,
# inverted SCLK (writes on the SCLK fall, like the register file) while playback is selected, which
# changes only with ENABLE=0 (both writers idle). Two generated clocks, physically exclusive; the
# SCLK alternative stays timed from the register file (it is NOT in the sclk false-path list).
set mem_clks {}
set mem_mux [get_pins -quiet -hierarchical *memory_clock_mux*/Z]
if {[llength $mem_mux]} {
    if {[llength $mem_mux] != 1} {error "Expected one egress memory clock mux"}
    create_generated_clock -name egress_mem_hcore -master_clock hcore -source $core_root -combinational $mem_mux
    create_generated_clock -name egress_mem_sclk -master_clock sclk -source [get_ports spi_sclk] -divide_by 1 -invert -add $mem_mux
    set_clock_groups -physically_exclusive -group egress_mem_hcore -group egress_mem_sclk
    set mem_clks {egress_mem_hcore}
}
set all_clk_names [concat {sclk ref hword h2d wtx wrx rftx rfrx ctw ctref ctdet} $fc_clks $host_clks $ingress_clks $egress_clks $mem_clks]

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
# Inside the LibreLane PnR flow (STEP_ID set) the corner libraries ARE the characterized in-window
# ones (verification/digital_hardening/config.json LIB/RSZ_CORNERS: setup on ss_032C_3v15, hold on
# ff_022C/ff_032C_3v35), so the flow optimizes against the signoff library itself, no derate.
# (Former flow: tt x 1.75 with repair_design at tt x 1.0 -- it left 2-5 ns slews at ss and never converged.)
if {[info exists ::env(STEP_ID)]} { set PT_LIB_CHARACTERIZED 1 }
# Characterized in-window libraries (verification/digital_hardening/libchar.py; ss/ff at 22/32 C and
# 3.15/3.35 V): the corner is in the Liberty itself, so no envelope derate is applied.
if {![info exists PT_LIB_CHARACTERIZED]} {
    set PT_LIB_CHARACTERIZED 0
    if {[info exists ::env(PT_LIB_CHARACTERIZED)]} { set PT_LIB_CHARACTERIZED $::env(PT_LIB_CHARACTERIZED) }
}
if {$PT_LIB_CHARACTERIZED} { set pt_envelope_derate 1.0 }
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
# wire_tx_data (pt_wiredtx D0..D39, AC-1 S3): the serializer loads D0..D19 at the WORD_CLK
# falling edge after WORD_CLK40 rises (0.4 x T20 = 0.2 x T40 after it, conservative by T20/5) and
# D20..D39 one 20-bit word later (0.7 x T40), setup 0.5 ns / hold 0.3 ns (integration/pt_wired_tx.sdc).
# The macro launches D0..D19 from WORD_CLK40-falling flops and D20..D39 from rising flops.
set wtx_lo {}
set wtx_hi {}
for {set i 0} {$i < 40} {incr i} {
    if {$i < 20} {lappend wtx_lo "wire_tx_data\[$i\]"} else {lappend wtx_hi "wire_tx_data\[$i\]"}
}
set_output_delay -clock wtx -max [expr {0.5 - 0.2 * $WTX_PERIOD}] [get_ports $wtx_lo]
set_output_delay -clock wtx -min [expr {-(0.2 * $WTX_PERIOD + 0.3)}] [get_ports $wtx_lo]
set_output_delay -clock wtx -max [expr {0.3 * $WTX_PERIOD + 0.5}] [get_ports $wtx_hi]
set_output_delay -clock wtx -min [expr {0.3 * $WTX_PERIOD - 0.3}] [get_ports $wtx_hi]
pt_io rfrx $RFRX_PERIOD {rf_rx_sample* rf_rx_valid} {}
pt_io rftx $RFTX_PERIOD {rf_tx_request} {rf_tx_sample* rf_tx_valid rf_mute}
pt_io ref  $REF_PERIOD  {calibration_above_target} {calibration_trial* cdr_freq_locked}
pt_io ctref $CTREF_PERIOD {ct_marker} {ct_armed ct_marker_seen ct_launched ct_arm_fault}
pt_io ctw  $CTW_PERIOD  {} {ct_word_clk ct_word_load ct_ser_run ct_bit_phase ct_qualified}
pt_io ctdet $CTDET_PERIOD {} {ct_det_div*}
# ct_det_clk is the detector's divided CLOCK (det_clk = gated clk / a / a&b of pt_ct_detect_div), not
# data: no register captures it against ctdet, so it is a generated clock at the port (its duty /
# pulse width come from the divider registers) instead of a data output delay (AC1_R4: -4.2 ns on
# a 0.2 x period budget that has no receiver).
create_generated_clock -name ctdet_out -master_clock ctdet -source [get_ports ct_det_clk_in] -divide_by 1 -add [get_ports ct_det_clk]

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
# The register file commits on the SCLK falling edge (rtl/pt_spi.sv, pt_mgmt sclk_regs), so the
# budget is referenced to that edge: launch at the fall, settle 0.8 period later.
set_output_delay [expr {0.2 * $SCLK_PERIOD}] -clock sclk -clock_fall [get_ports {analog_cfg* debug_cfg* island_en* atb0_sw* atb1_sw* rx_en_* clk_obs_oe wclk_obs_oe
    dbg_obs0* dbg_obs1* wdbg_obs* commit_toggle enable mode8 rf_trim* wire_trim* clock_trim* d2h_oe d2h_pdrv* d2h_sl
    en_eff* island_off*}]
# en_eff[10]/[11] also carry the REF-domain regulator hold (rtl/pt_vreg_seq.sv): an asynchronous level
# into the analog enables (a >= 50 us hold window), not an SCLK-cycle path.
set_false_path -from [get_clocks ref] -to [get_ports en_eff*]
# PD8: WIRED_ON from the analog bring-up controller, an asynchronous level ORed into island_on[0].
set_false_path -from [get_ports wired_on_ext]

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
# D2H: each pin is q_r ^ q_f, toggled by a hddr rising-edge or falling-edge flop (one word per
# hddr edge); the DDR forwarded clock d2h_clk_pin = c_r ^ c_f is built the same way (edge-aligned).
# Checked in sta_signoff as a skew window (arrival min/max of data vs clock pin); here only a
# launch-side budget so the resizer keeps the data and clock paths equally short.
# D2H is SOURCE-SYNCHRONOUS (timing closure 2026-11-11). At full rate (DDR, HOST_RATE_DIV 1) the
# forwarded D2H_CLK pin (c_r ^ c_f, edge-aligned like DQS; the FPGA centres it) is a generated clock
# and each data pin must change within +-D2H_SKEW of the clock pin edge it belongs to: the
# requirement is the data-to-clock skew at the macro pins, not the absolute insertion delay of
# hddr (the former hddr-referenced output delay failed by -7.7 ns on 3.6-7 ns of tree latency
# that the forwarded clock carries equally). Launch hddr rise/fall -> the next d2h_fwd edge one UI
# later (setup: data <= clock + S), hold against the same edge (data >= clock - S).
# Reduced rates (SDR forwarded clock = gated ~word_clk) keep the hddr-referenced budget (>= 12.8 ns periods).
if {![info exists D2H_SKEW]} { set D2H_SKEW [expr {0.2 * $HLINK_PERIOD}] }
set sdr_sel_q [get_pins -quiet -hierarchical *host.clk_out.cell/S]
if {$HOST_RATE_DIV == 1 && [llength $sdr_sel_q] == 1} {
    set_case_analysis 0 $sdr_sel_q
    create_generated_clock -name d2h_fwd -master_clock hddr -source $rate_mux -divide_by 1 -add [get_ports d2h_clk_pin]
    set_output_delay [expr {$HLINK_PERIOD - $D2H_SKEW}] -max -clock d2h_fwd [get_ports d2h_pin*]
    set_output_delay [expr {$HLINK_PERIOD - $D2H_SKEW}] -max -clock d2h_fwd -clock_fall -add_delay [get_ports d2h_pin*]
    set_output_delay [expr {$D2H_SKEW}] -min -clock d2h_fwd [get_ports d2h_pin*]
    set_output_delay [expr {$D2H_SKEW}] -min -clock d2h_fwd -clock_fall -add_delay [get_ports d2h_pin*]
    if {[llength [get_clocks -quiet hsdr]]} { set_false_path -from [get_clocks hsdr] -to [get_ports d2h_clk_pin] }
} else {
    set_output_delay [expr {0.2 * $HLINK_PERIOD}] -clock hddr [get_ports {d2h_pin* d2h_clk_pin}]
    set_output_delay [expr {0.2 * $HLINK_PERIOD}] -clock hddr -clock_fall -add_delay [get_ports {d2h_pin* d2h_clk_pin}]
}
# HB-1 two-group launch stagger (rtl/pt_cells.sv pt_stagger, pt_host_link): every D2H lane passes one
# kept mux; odd lanes can select a kept two-buf_1 delay (~0.4-0.8 ns, a deliberate fixed offset the
# FPGA IDELAY absorbs). Launch budgets and the signoff skew window are checked with the stagger off;
# the staggered-group offset is a report item (sta_signoff), not a window violation.
set stg_sel [get_pins -quiet -hierarchical *stagger*lane.cell/S]
if {[llength $stg_sel]} { set_case_analysis 0 $stg_sel }

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
foreach pat {*.wr_reset* *.rd_reset* *.wr_active* *.rd_active* *.release_state* *.e?.active* *host.h2d.hrs* *host.drs* *host.crs*} {
    foreach c [pt_cells $pat] {
        foreach pin [get_pins -quiet -of_objects $c -filter "direction == input"] {
            if {[lsearch -exact {RN SETN SN} [get_property $pin lib_pin_name]] >= 0} { lappend rst_sync_pins $pin }
        }
    }
}
if {[llength $rst_sync_pins]} { set_false_path -to $rst_sync_pins }
# 1c. Rate-switch hold (pt_host_rate_clock hold_n, hword domain) asynchronously resets the host
#     link and transport core. Its release reaches every other domain only through a reset
#     synchronizer (host.drs for hddr, host.crs for hcore, host.h2d.hrs, the FIFO and ENABLE
#     synchronizers); only its own hword domain is timed. Likewise the hcore-released core reset
#     (host.crs, core_rst_n) is asynchronous to the wired/RF domains of the core, whose flops are
#     additionally held by their synchronized ENABLE (pt_sync_bit / pt_enable_release e2..e5).
set hold_src [pt_cells *host_rate.hold_n*]
if {[llength $hold_src]} {
    foreach c [all_clocks] {
        if {[get_name $c] ne "hword"} { set_false_path -from $hold_src -to $c }
    }
}
# (synthesis names a flop after the net it drives: host.crs[1] may appear as core_rst_n_*)
set crs_src [concat [pt_cells *host.crs*] [pt_cells core_rst_n_*] [pt_cells *.core_rst_n_*]]
if {[llength $crs_src]} {
    foreach c [all_clocks] {
        if {[lsearch -exact {hcore} [get_name $c]] < 0} { set_false_path -from $crs_src -to $c }
    }
}
# 2. Gray-coded async FIFO pointers (pt_async_fifo rg1 / wg1): bounded to the faster of the two
#    clock periods, so the pointer bits arrive within one sampling period.
#    Only data paths launched by the other side's clock are bounded (the reset-release recovery
#    paths into the same flops stay single-cycle in their own domain).
set clock_periods [dict create hword $HWORD_PERIOD hddr $HDDR_PERIOD hcore $HCORE_PERIOD \
                              h2d $H2D_PERIOD wtx $WTX_PERIOD wrx $WRX_PERIOD rftx $RFTX_PERIOD rfrx $RFRX_PERIOD \
                              ingress_wrx $WRX_PERIOD ingress_rfrx $RFRX_PERIOD egress_wtx $WTX_PERIOD egress_rftx $RFTX_PERIOD]
# H2D quad FIFO (pin clock -> hcore): pointers, then storage read by hcore.
foreach {f wr rd} [list *host.h2d h2d hcore] {
    set lim [expr {min([dict get $clock_periods $wr], [dict get $clock_periods $rd])}]
    set r1 [pt_cells "${f}.rg1*"]
    if {[llength $r1]} { pt_bound_xing $lim -from [get_clocks $rd] -to $r1 }
    set w1 [pt_cells "${f}.wg1*"]
    if {[llength $w1]} { pt_bound_xing $lim -from [get_clocks $wr] -to $w1 }
    set m [pt_cells "${f}.mem*"]
    if {[llength $m]} { pt_bound_xing [dict get $clock_periods $rd] -from $m -to [get_clocks $rd] }
}
# 3. Shared ingress (selected input clock -> hcore) and egress (hcore -> selected output clock):
#    every Gray crossing and storage read, for each selected mode. A word is written at least
#    two reader-domain cycles before its Gray pointer can be seen; storage reads are bounded to
#    one reader period, pointers to the faster period.
foreach {f wrs rds} [list *core.ingress $ingress_clks hcore *core.egress hcore $egress_clks] {
    foreach wr $wrs {
        foreach rd $rds {
            set lim [expr {min([dict get $clock_periods $wr], [dict get $clock_periods $rd])}]
            set r1 [pt_cells "${f}.rg1*"]
            if {[llength $r1]} { pt_bound_xing $lim -from [get_clocks $rd] -to $r1 }
            set w1 [pt_cells "${f}.wg1*"]
            if {[llength $w1]} { pt_bound_xing $lim -from [get_clocks $wr] -to $w1 }
            set m [pt_cells "${f}.mem*"]
            if {[llength $m]} { pt_bound_xing [dict get $clock_periods $rd] -from $m -to [get_clocks $rd] }
        }
    }
}
# 4. MEMORY v3 banks (sharing S1): ingress capture entries are read over SPI (peek port) only after
#    the synchronized capture_done (regfile c1/c2) with the bank stopped (no further writes);
#    playback entries are written on the SCLK fall with ENABLE=0 and read by the owner clock only
#    after ENABLE=1 releases the reader (synchronized). Protocol-protected; bounded to the reader.
set cb [pt_cells {*core.ingress.mem*}]
if {[llength $cb]} { pt_bound_xing $SCLK_PERIOD -from $cb -to [get_clocks sclk] }
# capture_done is a pt_core output register; synthesis names it after the pt_digital net
# (digital.capture_done_<cell>), so match it anywhere (AC1 run0: the bound silently missed it).
set cd [pt_cells {*capture_done*}]
if {[llength $cd]} { pt_bound_xing $SCLK_PERIOD -from $cd -to [get_clocks sclk] }
if {[llength $mem_clks]} {
    foreach c [concat $egress_clks hcore] { set_false_path -from [get_clocks egress_mem_sclk] -to [get_clocks $c] }
}
# 4b. pt_freq_count (fca, fcb): Gray-coded source count into the reference domain (bounded like FIFO
#     pointers); handshake-held {count, lost, locked, diff} into SCLK (held stable while req != ack).
foreach inst {fca fcb} {
    set g [pt_cells "*${inst}.s1*"]
    if {[llength $g]} { pt_bound_xing $REF_PERIOD -from [get_clocks $fc_clks] -to $g }
    set h [pt_cells "*${inst}.hold*"]
    if {[llength $h]} { pt_bound_xing $SCLK_PERIOD -from $h -to [get_clocks sclk] }
    # Window evaluation: snapshot, fb_prev and the captured configuration are loaded at least 5
    # reference cycles before the result registers that use them (window end -> ev_cnt countdown;
    # a configuration capture inside that interval suppresses the metric update). Checked by
    # sim/tb_pt_freq_count.sv eval_window.
    # cfg_src_r (source) is not in the list: a source change must clear the state through `run` in one
    # cycle. Synthesis names r_diff/r_count after the `cur` bus and r_locked after locked_ref.
    set evf [concat [pt_cells "*${inst}.snap_*"] [pt_cells "*${inst}.fb_prev*"] [pt_cells "*${inst}.cfg_r*"]]
    # good / r_locked change only at ev_go (or are held clear while !run), so their own update
    # (good != need, good + 1 >= need) is the same window-evaluation multicycle.
    set evf [concat $evf [pt_cells "*${inst}.good*"] [pt_cells "*${inst}.r_locked*"]]
    if {$inst eq "fcb"} { set evf [concat $evf [pt_cells "cdr_freq_locked*"]] }
    set evt {}
    foreach pat {r_diff* r_count* cur* good* r_locked* locked_ref* r_lost* fb_prev*} {
        set evt [concat $evt [pt_cells "*${inst}.$pat"]]
    }
    # instance b's r_locked drives the cdr_freq_locked port and synthesis names the flop after the
    # port (cdr_freq_locked_<cell>_Q): include it, or the 5-cycle window rule silently misses it
    # (AC1_R4: ref -26.5 ns on fcb.snap_h -> cdr_freq_locked, a 32-level single-cycle path).
    if {$inst eq "fcb"} { set evt [concat $evt [pt_cells "cdr_freq_locked*"]] }
    if {[llength $evf] && [llength $evt]} {
        set_multicycle_path 5 -setup -from $evf -to $evt
        set_multicycle_path 4 -hold -from $evf -to $evt
    }
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
# ---------------- SPI write decode (timing closure 2026-11-11). pt_spi captures the command byte (cmd_r,
# 8th rising edge) and the address (rd_addr = wr_addr, 16th rising edge) into registers held until CS_N
# rises; the write lands on the falling edge after the 32nd rising edge, >= 16 SCLK periods later.
# Only the data word (shift[15:0]) and count==32 are half-period paths into the register file.
# The read path rd_addr -> rd_data -> spi.read_value/miso_bit is NOT relaxed (excluded below).
# (synthesis names the address flops after the register-file port they drive: regs.wr_addr / regs.rd_addr)
set spi_held [concat [pt_cells *control.spi.rd_addr*] [pt_cells *control.regs.rd_addr*] [pt_cells *control.regs.wr_addr*] \
                     [pt_cells *control.rd_addr*] [pt_cells *control.wr_addr*] [pt_cells *control.spi.cmd_r*]]
set spi_wdst [pt_cells *control.regs.*]
if {[llength $spi_held] && [llength $spi_wdst]} {
    set_multicycle_path 4 -setup -end -from $spi_held -to $spi_wdst
    set_multicycle_path 3 -hold -end -from $spi_held -to $spi_wdst
    if {[llength $mem_clks]} {
        set_multicycle_path 4 -setup -end -from $spi_held -to [get_clocks egress_mem_sclk]
        set_multicycle_path 3 -hold -end -from $spi_held -to [get_clocks egress_mem_sclk]
    }
}

# SPI read candidates (pt_spi cand0/cand1, 16th rising edge): register-file CONFIGURATION registers
# (falling-edge flops) change only at write edges of earlier transactions (>= 16 SCLK before the read
# capture), so they are multicycle sources; only rd_hi (the shift register, one full period) and the
# synchronized STATUS stages (st*/s*/c*/pg*/on*/f*, which can change on any SCLK fall) stay single-cycle.
set rd_cand [concat [pt_cells *control.spi.cand0*] [pt_cells *control.spi.cand1*]]
set rd_cfg {}
foreach c [pt_cells *control.regs.*] {
    set n [get_full_name $c]
    if {![regexp {regs\.(st[12]_|s[12]\[|s[12]_|c[12]_|pg[12]|on[12]|f[12]|wr_|rd_)} $n]} { lappend rd_cfg $c }
}
if {[llength $rd_cand] && [llength $rd_cfg]} {
    set_multicycle_path 8 -setup -end -from $rd_cfg -to $rd_cand
    set_multicycle_path 7 -hold -end -from $rd_cfg -to $rd_cand
}

# ---------------- Pattern generator/checker configuration (debug.pattern mode/invert/user word):
# synchronized copies of fields that change only by COMMIT while ENABLE=0, when the generator is held
# in reset (prbs_rst_n = rst_n && synchronized ENABLE) and the checker is disabled; ENABLE needs a
# later SPI transaction (>= 32 SCLK), so they are settled long before either runs. Static, not timed.
set pat_cfg [concat [pt_cells *pat_tx_cfg*] [pt_cells *pat_rx_cfg*] [pt_cells *ptxc.q*] [pt_cells *prxc.q*]]
if {[llength $pat_cfg]} { set_false_path -from $pat_cfg }

# ---------------- Host-link mode (debug.host_link.mode) synchronized copies: stopped-only (the regfile
# accepts it only while ENABLE=0; the H2D/D2H paths are idle), so they are static for timing.
set hl_mode [concat [pt_cells *h2d.mode_h*] [pt_cells *h2d.smh.q*] [pt_cells *host.mode_d*]]
if {[llength $hl_mode]} { set_false_path -from $hl_mode }

# ---------------- Exclusive-owner and handshake crossings (timing closure 2026-11-11). Each one was
# timed as a synchronous path with an arbitrary common-period alignment in AC1_R4.
# (a) Shared banks: the egress/ingress bank clocks are a stopped-only mux of the wired and the RF
#     owner clock (payload_iq changes only while ENABLE=0 holds both FIFO sides in reset). The
#     inactive owner's logic never launches into, or captures from, the selected bank clock.
foreach {a b} {rftx egress_wtx rfhalf egress_wtx wtx egress_rftx wrx ingress_rfrx ingress_wrx rfrx ingress_wrx rftx} {
    if {[llength [get_clocks -quiet $a]] && [llength [get_clocks -quiet $b]]} { set_false_path -from [get_clocks $a] -to [get_clocks $b] }
}
# (b) Playback memory: SPI writes (egress_mem_sclk) only with play=1, transport writes (hcore) only
#     with play=0; play is stopped-only (ENABLE=0). sclk -> * is already false (static registers).
if {[llength $mem_clks]} {
    set_false_path -from [get_clocks hcore] -to [get_clocks egress_mem_sclk]
    # SPI playback writes: the array captures on the SCLK fall after the 32nd rising edge of a 0x22
    # write (memory_write). Every SCLK-domain input of that write (index, staged play_i/play_h,
    # playback_enable, ENABLE: falling-edge registers that change only at OTHER transactions' write
    # edges, where memory_write = 0; shift data/count stop at the 32nd edge) is stable from >= 1 SCLK
    # before to >= 1 SCLK after it, so the same-edge hold check against the ~10 ns later array clock
    # (mux + tree) is not a real race.
    set_false_path -hold -from [get_clocks sclk] -to [get_clocks egress_mem_sclk]
}
# (c) Fast gain (opcode4) toggle handshake. hcore -> rfrx: gain_arg is held from the toggle flip
#     until the gain-status frame; the toggle crosses through gain_rx.t1/t2 (two flops), so gain_arg
#     is sampled >= 2 rf_rx_clk periods after it settled: bounded to one rfrx period, no hold.
#     rfrx -> hcore: mark_ptr/gap are written one clock before mark_toggle flips and are stable
#     until the next gain command; mark_toggle crosses through core.gm (pt_sync_bit).
set g_t1 [pt_cells *gain_rx.t1*]
if {[llength $g_t1]} { set_false_path -to $g_t1 }
set g_arg [pt_cells *gain_arg*]
if {[llength $g_arg]} { pt_bound_xing $RFRX_PERIOD -from $g_arg -to [get_clocks rfrx] }
# Clock-level bounds: the only rfrx -> hcore data are mark_ptr / gap (synthesis names those flops after
# their consumer, e.g. frame_tx.engine.gap, so cell patterns are fragile) plus mark_toggle into the
# core.gm synchronizer; the only hcore -> rfrx data are gain_arg and gain_toggle (into gain_rx.t1).
# mark_ptr/gap settle >= 1 rf_rx_clk before mark_toggle flips; the toggle then needs the two core.gm
# synchronizer flops before mk_seen can use them, so two hcore periods bound the data.
pt_bound_xing [expr {2.0 * $HCORE_PERIOD}] -from [get_clocks rfrx] -to [get_clocks hcore]
pt_bound_xing $RFRX_PERIOD -from [get_clocks hcore] -to [get_clocks rfrx]
# (d) The applied fast gain (rf_rx_clk levels rx_gain/rx_gain_active) overrides the LNA/PGA bits of
#     the static analog_cfg/debug_cfg outputs. Analog controls with no capturing clock: the gain
#     command discards the next GAIN_SETTLE (20) samples, so one RF sample period from the rfrx
#     register to the pin is the budget (the sclk output delay is not a requirement for these).
set_max_delay [expr {$RFRX_PERIOD + 0.2 * $SCLK_PERIOD}] -from [get_clocks rfrx] -to [get_ports {analog_cfg* debug_cfg*}]
set_false_path -hold -from [get_clocks rfrx] -to [get_ports {analog_cfg* debug_cfg*}]

if {[info exists ::env(STEP_ID)] && $::env(STEP_ID) eq "OpenROAD.CTS"} {
    if {[llength $egress_clks]} { delete_clock [get_clocks egress_rftx] }
    if {[llength $ingress_clks]} { delete_clock [get_clocks ingress_rfrx] }
    if {[llength $mem_clks]} { delete_clock [get_clocks egress_mem_sclk] }
    # pt_freq_count block clocks: the six source alternatives share one buffer output per instance
    foreach inst {fca fcb} { for {set i 1} {$i < 6} {incr i} {
        if {[llength [get_clocks -quiet ${inst}_blk$i]]} { delete_clock [get_clocks ${inst}_blk$i] } } }
    puts "PT_CTS_SHARED_BANKS: building one physical tree per shared bank; dual-mode STA resumes after CTS"
}
