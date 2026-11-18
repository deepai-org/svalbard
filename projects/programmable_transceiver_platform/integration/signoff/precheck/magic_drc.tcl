# Magic DRC of one GDS exactly as LibreLane 3.1.0.dev3 Magic.DRC does it inside the wafer.space precheck 1.7.4
# (scripts/magic/drc.tcl: gds maskhints, flatglob list from precheck.py, drc(full), euclidean, listall why).
#   magic -dnull -noconsole -rcfile <pdk>/libs.tech/magic/gf180mcuD.magicrc magic_drc.tcl
# env: CURRENT_GDS, DESIGN_NAME, REPORT (output text report)
crashbackups disable
locking disable
units internal
gds noduplicates true
gds readonly true
gds maskhints true
foreach g {*_CDNS_* COMP_FILL COMP_fill_cell POLY2_FILL Poly2_fill_cell *$$* M1_N* M1_P* M2_M1* M3_M2* nmos_5p0* nmos_1p2*
           pmos_5p0* pmos_1p2* via1_* ypass_gate* G_ring_* dcap_103* din_* mux821_* rdummy_* pmoscap_* xdec_* ypredec*
           xpredec* prexdec_* xdec8_* xdec16_* xdec32_* sa_*} { gds flatglob $g }
gds read $::env(CURRENT_GDS)
set fout [open $::env(REPORT) w]
set oscale [cif scale out]
set cell_name $::env(DESIGN_NAME)
magic::suspendall
load $cell_name
select top cell
drc euclidean on
drc style drc(full)
drc check
set drcresult [drc listall why]
set count 0
puts $fout "$cell_name"
puts $fout "----------------------------------------"
foreach {errtype coordlist} $drcresult {
    puts $fout $errtype
    puts $fout "----------------------------------------"
    foreach coord $coordlist {
        puts $fout [format " %.3fum %.3fum %.3fum %.3fum" [expr {$oscale * [lindex $coord 0]}] [expr {$oscale * [lindex $coord 1]}] [expr {$oscale * [lindex $coord 2]}] [expr {$oscale * [lindex $coord 3]}]]
        incr count
    }
    puts $fout "----------------------------------------"
}
puts $fout "\[INFO\] COUNT: $count"
close $fout
puts stdout "\[INFO\] COUNT: $count"
quit -noprompt
