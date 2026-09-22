import pathlib,subprocess
src=pathlib.Path('/src/verification');out=pathlib.Path('/out')
for corner in ('tt_025C_3v30','ff_n40C_3v60','ss_125C_3v00'):
 for kind,template in [('setup','block_capture_timing.tcl'),('hold','block_capture_hold.tcl')]:
  text=(src/template).read_text()
  body=text[text.index('create_clock'):].replace('/out/capture-pins.tcl','/mapped/capture-pins.tcl')
  body=body.replace('# Earliest ready', 'set_propagated_clock [all_clocks]\n# Earliest ready').replace('# Illustrative internal', 'set_propagated_clock [all_clocks]\n# Illustrative internal')
  header=f'''read_liberty /pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__{corner}.lib
read_db /out/digital.odb
set_wire_rc -signal -layer Metal3
set_wire_rc -clock -layer Metal4
estimate_parasitics -placement
'''
  script=out/(corner+'-'+kind+'.tcl');script.write_text(header+body)
  with (out/(corner+'-'+kind+'.log')).open('w') as log:
   subprocess.run(['openroad','-no_init','-exit',str(script)],stdout=log,stderr=subprocess.STDOUT,check=True)
