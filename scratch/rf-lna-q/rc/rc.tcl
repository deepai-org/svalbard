crashbackups stop
drc off
gds read in.gds
load pt_lna
flatten pt_lna_flat
load pt_lna_flat
select top cell
extract do capacitance
extract do coupling
extract do resistance
extract all
ext2sim labels on
ext2sim
extresist simplify off
extresist ignore VSS
extresist ignore VDD
extresist ignore VSUBS
extresist all
ext2spice lvs
ext2spice hierarchy off
ext2spice format ngspice
ext2spice cthresh 0
ext2spice rthresh 0
ext2spice extresist on
ext2spice subcircuit top on
ext2spice -o pt_lna_flat.rc.spice
quit -noprompt
