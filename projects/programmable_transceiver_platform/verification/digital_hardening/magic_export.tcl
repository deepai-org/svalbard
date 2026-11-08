# GDS export of the routed pt_digital_macro with the analog image's Magic 8.3.678
# (spec/block-deliverables.md "GDS export rule"), mirroring LibreLane's scripts/magic/def/mag_gds.tcl:
# standard cells read from the PDK GDS (read-only), annotated by their LEF, then the routed DEF.
set sc $::env(PDKPATH)/libs.ref/gf180mcu_fd_sc_mcu7t5v0
drc off
crashbackups disable
locking disable
gds noduplicates true
gds readonly true
gds rescale false
gds read $sc/gds/gf180mcu_fd_sc_mcu7t5v0.gds
foreach f [glob $sc/lef/*.lef] { lef read $f }
load (NEWCELL)
lef read $sc/techlef/gf180mcu_fd_sc_mcu7t5v0__nom.tlef
def read /work/pt_digital_macro.def -noblockage
load pt_digital_macro
select top cell
cif ostyle gdsii
gds nodatestamp yes
gds write /work/pt_digital_macro.gds
puts "EXPORT_DONE [box values]"
quit -noprompt
