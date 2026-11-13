# pt_cts_h2d.tcl -- H2D capture clock kept out of CTS (TC13 r4c, coordinator decision "option a").
#
# The 30 H2D pin-capture flops are clocked by a hand-built, hand-placed distribution matched to the data
# path: h2d_clk -> host.h2d.cap_root (clkbuf_8) -> one fixed clkbuf_8 per capture row (hio_cbr: rising
# r flops, hio_cbf: falling f flops, hio_cbh: falling fh flops) -> flops. OpenROAD CTS has no per-clock
# exclusion and refuses dont_touch clock nets, and on h2d_cap it built a 3-level clkbuf_16 tree (~2.5 ns
# insertion against ~1 ns of data path: hold -0.99 ns). This file wraps clock_tree_synthesis: CTS runs
# as configured, then every buffer CTS inserted below cap_root is removed and the fixed connections are
# restored, and the hand-built nets are marked dont_touch for the later resizer steps.
#
# Sourced from integration/pt_digital_macro.sdc only inside LibreLane's CTS step.

proc pt_h2d_inst {name} {
    set i [[ord::get_db_block] findInst $name]
    if {$i eq "NULL" || $i eq ""} { error "pt_cts_h2d: instance $name not found" }
    return $i
}

proc pt_h2d_out_net {inst} {
    foreach it [$inst getITerms] {
        if {[$it isOutputSignal]} { return [$it getNet] }
    }
    return "NULL"
}

proc pt_h2d_clock_iterm {inst} {
    foreach p {CLK CLKN} {
        set it [$inst findITerm $p]
        if {$it ne "NULL" && $it ne ""} { return $it }
    }
    error "pt_h2d: no clock pin on [$inst getName]"
}

proc pt_h2d_reconnect {it net} {
    set cur [$it getNet]
    if {$cur ne "NULL" && $cur ne "" && [$cur getName] eq [$net getName]} { return 0 }
    $it disconnect
    $it connect $net
    return 1
}

proc pt_h2d_restore {} {
    set block [ord::get_db_block]
    set root [pt_h2d_inst host.h2d.cap_root.cell]
    set root_net [pt_h2d_out_net $root]
    # buffers CTS added under cap_root: walk the clock fan-out from cap_root through any buffer that is
    # not one of the fixed cells
    set fixed {host.h2d.hio_cbr.cell host.h2d.hio_cbf.cell host.h2d.hio_cbh.cell host.h2d.core_root.cell}
    set cts_bufs {}
    set todo [list $root_net]
    while {[llength $todo]} {
        set n [lindex $todo 0]; set todo [lrange $todo 1 end]
        foreach it [$n getITerms] {
            if {![$it isInputSignal]} { continue }
            set i [$it getInst]; set nm [$i getName]
            if {[lsearch -exact $fixed $nm] >= 0} { continue }
            set m [[$i getMaster] getName]
            if {[string match *__clkbuf_* $m] || [string match *__buf_* $m] || [string match *__clkinv_* $m]} {
                lappend cts_bufs $i
                set o [pt_h2d_out_net $i]
                if {$o ne "NULL"} { lappend todo $o }
            }
        }
    }
    # also walk below each fixed row buffer (CTS may have built a subtree there)
    set rowmap [dict create cbr {host.h2d.cap\[*\].cr.p.lr} cbf {host.h2d.cap\[*\].cf.n.lf} cbh {host.h2d.fhh\[*\].c.n.lf}]
    dict for {cb pat} $rowmap {
        set cbi [pt_h2d_inst host.h2d.hio_$cb.cell]
        set todo [list [pt_h2d_out_net $cbi]]
        while {[llength $todo]} {
            set n [lindex $todo 0]; set todo [lrange $todo 1 end]
            foreach it [$n getITerms] {
                if {![$it isInputSignal]} { continue }
                set i [$it getInst]; set m [[$i getMaster] getName]
                if {[string match *__clkbuf_* $m] || [string match *__buf_* $m] || [string match *__clkinv_* $m]} {
                    lappend cts_bufs $i
                    set o [pt_h2d_out_net $i]
                    if {$o ne "NULL"} { lappend todo $o }
                }
            }
        }
    }
    # restore the fixed connections
    set moved 0
    foreach nm $fixed { incr moved [pt_h2d_reconnect [[pt_h2d_inst $nm] findITerm I] $root_net] }
    set nflops 0
    dict for {cb pat} $rowmap {
        set cb_net [pt_h2d_out_net [pt_h2d_inst host.h2d.hio_$cb.cell]]
        foreach i [$block getInsts] {
            if {[string match $pat [$i getName]]} {
                incr moved [pt_h2d_reconnect [pt_h2d_clock_iterm $i] $cb_net]
                incr nflops
            }
        }
    }
    if {$nflops != 30} { error "pt_cts_h2d: expected 30 capture flops, found $nflops" }
    # remove the now unloaded CTS buffers (and their output nets)
    set removed 0
    foreach i [lsort -unique $cts_bufs] {
        set o [pt_h2d_out_net $i]
        set loads 0
        if {$o ne "NULL"} { foreach it [$o getITerms] { if {[$it isInputSignal]} { incr loads } } }
        if {$loads == 0} {
            odb::dbInst_destroy $i
            if {$o ne "NULL"} { odb::dbNet_destroy $o }
            incr removed
        } else {
            # a CTS buffer that still feeds something outside the capture set
            puts "\[WARNING PT-H2D\] CTS buffer [$i getName] still has $loads loads under cap_root"
        }
    }
    $root_net setDoNotTouch 1
    foreach cb {cbr cbf cbh} { [pt_h2d_out_net [pt_h2d_inst host.h2d.hio_$cb.cell]] setDoNotTouch 1 }
    puts "\[INFO PT-H2D\] H2D capture clock restored: $nflops flops, $moved pins reconnected, $removed CTS buffers removed"
}

if {[info commands clock_tree_synthesis] ne "" && [info commands pt_orig_clock_tree_synthesis] eq ""} {
    rename clock_tree_synthesis pt_orig_clock_tree_synthesis
    proc clock_tree_synthesis {args} {
        pt_orig_clock_tree_synthesis {*}$args
        pt_h2d_restore
    }
}
