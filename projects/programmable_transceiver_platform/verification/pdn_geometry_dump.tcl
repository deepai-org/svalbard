read_db /input/digital-pdn.odb
set block [ord::get_db_block]
set file [open /out/rectangles.tsv w]
foreach name {VDD_CORE VSS_CORE} {
 set net [$block findNet $name]
 foreach swire [$net getSWires] {
  foreach shape [$swire getWires] {
   if {[$shape isVia]} {
    set via [$shape getBlockVia]
    if {$via == "NULL"} {set via [$shape getTechVia]}
    lassign [$shape getViaXY] x y
    foreach box [$via getBoxes] {
     puts $file "$name\t[[$box getTechLayer] getName]\t[expr {$x+[$box xMin]}]\t[expr {$y+[$box yMin]}]\t[expr {$x+[$box xMax]}]\t[expr {$y+[$box yMax]}]\tVIA"
    }
   } else {
    puts $file "$name\t[[$shape getTechLayer] getName]\t[$shape xMin]\t[$shape yMin]\t[$shape xMax]\t[$shape yMax]\tSTRIPE"
   }
  }
 }
}
close $file
puts "PDN_GEOMETRY_DUMP_COMPLETE"
exit
