crashbackups stop
gds read pt_decap_tile.gds
load pt_decap_tile
select top cell
expand
drc check
drc catchup
puts "TILE_DRC [drc list count total]"
puts [drc listall why]
extract all
ext2spice lvs
ext2spice -o pt_decap_tile_lvs.spice
ext2spice cthresh 0
ext2spice -o pt_decap_tile_ext.spice
quit -noprompt
