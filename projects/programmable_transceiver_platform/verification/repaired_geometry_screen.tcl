read_db /input/repaired.odb
check_placement -verbose
write_def /out/digital.def
set block [ord::get_db_block]
set dbu [$block getDbUnitsPerMicron]
set count 0
set area 0.0
set unplaced 0
set geometry [open /out/cells.tsv w]
foreach inst [$block getInsts] {
 set box [$inst getBBox]
 puts $geometry "[$inst getName]\t[$box xMin]\t[$box yMin]\t[$box xMax]\t[$box yMax]\t[$inst getOrient]"
 incr count
 set master [$inst getMaster]
 set area [expr {$area + double([$master getWidth])*[$master getHeight]/$dbu/$dbu}]
 if {![$inst isPlaced]} {incr unplaced}
}
close $geometry
set file [open /out/placement-counts.json w]
puts $file "{\"instances\": $count, \"cell_area_um2\": $area, \"unplaced\": $unplaced, \"requested_region_um2\": 2295000}"
close $file
foreach phase {before after} {
 if {$phase == "after"} {
  add_global_connection -net VDD_CORE -inst_pattern .* -pin_pattern {^(VDD|VNW)$} -power
  add_global_connection -net VSS_CORE -inst_pattern .* -pin_pattern {^(VSS|VPW)$} -ground
  global_connect
 }
set supplies [open /out/supply-$phase.tsv w]
set signals [open /out/signals-$phase.tsv w]
foreach inst [$block getInsts] {
 foreach term [$inst getITerms] {
  set pin [$term getMTerm]
  set kind [$pin getSigType]
   set net [$term getNet]
   set name "UNCONNECTED"
   if {$net != "NULL"} {set name [$net getName]}
  if {$kind == "POWER" || $kind == "GROUND"} {
   puts $supplies "[$inst getName]\t[[$inst getMaster] getName]\t[$pin getName]\t$kind\t$name"
  } else {
   puts $signals "[$inst getName]\t[$pin getName]\t$name"
  }
 }
}
close $signals
close $supplies
}
write_db /out/supply-connected.odb
write_def /out/supply-connected.def

exit
