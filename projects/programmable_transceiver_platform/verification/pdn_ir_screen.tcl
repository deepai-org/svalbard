read_liberty /pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.lib
read_db /input/digital-pdn.odb
set voltage 3.3
set current [expr {$::env(PT_CURRENT_MA)/1000.0}]
set instances [[ord::get_db_block] getInsts]
set power [expr {$voltage*$current/[llength $instances]}]
foreach inst $instances {set_pdnsim_inst_power -inst [$inst getName] -power $power}
set_pdnsim_net_voltage -net VDD_CORE -voltage $voltage
set_pdnsim_net_voltage -net VSS_CORE -voltage 0
puts "LOAD_ASSUMPTION instances=[llength $instances] total_current_A=$current per_instance_W=$power"
foreach {net y v} {VDD_CORE 61.76 3.3 VSS_CORE 21.76 0.0} {
 set source [open /out/$net.csv w]
 puts $source "20.08,$y,2,$v"
 close $source
 analyze_power_grid -net $net -vsrc /out/$net.csv -voltage_file /out/$net-voltage.csv
 write_pg_spice -net $net -vsrc /out/$net.csv /out/$net.spice
}
puts "IR_SCREEN_COMPLETE"
exit
