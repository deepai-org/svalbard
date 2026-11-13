# The PDK fill_all.rb passes -rd threads (a String) straight to TilingProcessor#threads= and dies.
# Wrapper: convert, then run the unmodified PDK script.   -rd thr=N -rd input= -rd output=
$threads = ($thr || '2').to_i
load '/foss/pdks/gf180mcuD/libs.tech/klayout/tech/scripts/fill_all.rb'
