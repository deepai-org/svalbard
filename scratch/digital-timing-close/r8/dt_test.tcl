# crash test: stock post-GRT timing repair with the FIRM host-link flops as dont-touch instances
set ::env(_TCL_ENV_IN) /out/design/runs/R8A/41-openroad-resizertimingpostgrt/_env.tcl
set ::env(SCRIPTS_DIR) /usr/local/lib/python3.12/dist-packages/librelane/scripts
set i 0
foreach c {max_ss_032C_3v15:ss_032C_3v15 min_ff_022C_3v35:ff_022C_3v35 min_ff_n40C_3v60:ff_n40C_3v60} {
  lassign [split $c :] n l; set ::env(_LIB_CORNER_$i) "$n /out/design/lib/gf180mcu_fd_sc_mcu7t5v0__$l.lib"; incr i }
set ::env(_SDC_IN) /out/design/pt_digital_macro.sdc
set ::env(STEP_DIR) /out/dt_test
set ::env(_PNR_EXCLUDED_CELLS) {gf180mcu_fd_sc_mcu7t5v0__mux2_1 gf180mcu_fd_sc_mcu7t5v0__oai33_2 gf180mcu_fd_sc_mcu7t5v0__dly* gf180mcu_fd_sc_mcu7t5v0__xor3* gf180mcu_fd_sc_mcu7t5v0__xnor3* gf180mcu_fd_sc_mcu7t5v0__or4*}
source $::env(SCRIPTS_DIR)/openroad/common/io.tcl
set fh [open /r8/firm_flops.txt]; set ff [split [string trim [read $fh]] "\n"]; close $fh
set ::env(RSZ_DONT_TOUCH_LIST) [concat $::env(RSZ_DONT_TOUCH_LIST) $ff]
foreach k {SAVE_ODB SAVE_DEF SAVE_SDC SAVE_NL SAVE_PNL} { set ::env($k) /out/dt_test/x.[string tolower [string range $k 5 end]] }
rename source _src
proc source {f} { if {[string match */common/io.tcl $f]} { return }; uplevel 1 [list _src $f] }
_src $::env(SCRIPTS_DIR)/openroad/rsz_timing_postgrt.tcl
