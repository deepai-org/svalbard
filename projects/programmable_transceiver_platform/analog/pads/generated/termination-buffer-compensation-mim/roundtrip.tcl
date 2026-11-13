crashbackups stop
gds read feedforward_mim.gds
load feedforward_mim
select top cell
expand
drc check
drc catchup
puts "MIM_DRC [drc list count total]"
extract all
ext2spice lvs
ext2spice cthresh 0
ext2spice
quit -noprompt
