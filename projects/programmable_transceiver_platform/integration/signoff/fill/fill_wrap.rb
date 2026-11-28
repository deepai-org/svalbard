# The PDK fill_all.rb hands -rd threads (a String) to TilingProcessor#threads= and dies. Convert, then load the unmodified
# PDK script.   klayout -b -r fill_wrap.rb -rd input=.. -rd output=.. -rd thr=N -rd pdkscripts=/pdk/scripts [-rd comp_seam=0]
$threads = ($thr || '1').to_i
load File.join($pdkscripts, 'fill_all.rb')
# Second COMP pass on a 330 um tile grid (comp_seam, default on). The PDK fill drops a 5 x 5 cell that straddles a 400 um
# tile border (the grid is centred on the die), so a narrow clear area cut by a border stays empty: pt_rf plan-rf8b DCF.1a,
# 21 x 22 um between pt_lo_lf and pt_lo_pfdcp, cut by the border at y 761. The second pass reads the first pass's dummy
# COMP (3 um DCF.2a spacing) and only fills what the seams left; it runs the PDK fill_comp.rb text with the tile size changed.
if ($comp_seam || '1') != '0'
  src = File.read(File.join($pdkscripts, 'fill_comp.rb'))
  raise 'fill_comp.rb: tile_size line not found' unless src.sub!(/^tile_size = 400$/, 'tile_size = 330')
  puts 'Starting COMP seam pass (330 um tiles)...'
  eval(src, TOPLEVEL_BINDING, 'fill_comp.rb (seam pass)')
  $ly.write($output)
end
