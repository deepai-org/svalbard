crashbackups stop
load workspace
units internal
set cell [magic::gencell_makecell gf180mcu::cap_mim_2p0fF w 38.73 l 38.73]
load $cell
save feedforward_mim
select top cell
expand
drc check
drc catchup
puts "MIM_DRC [drc list count total]"
extract all
ext2spice lvs
ext2spice cthresh 0
ext2spice
gds write feedforward_mim.gds
quit -noprompt
