# The PDK fill_all.rb hands -rd threads (a String) to TilingProcessor#threads= and dies. Convert, then load the unmodified
# PDK script.   klayout -b -r fill_wrap.rb -rd input=.. -rd output=.. -rd thr=N -rd pdkscripts=/pdk/scripts
$threads = ($thr || '1').to_i
load File.join($pdkscripts, 'fill_all.rb')
