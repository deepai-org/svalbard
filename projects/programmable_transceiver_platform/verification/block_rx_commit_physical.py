import pathlib,subprocess
out=pathlib.Path('/out')
body=pathlib.Path('/src/verification/block_rx_timing_constraints.tcl').read_text()
body=body.replace('# Provisional internal', 'set_propagated_clock [all_clocks]\nset_clock_uncertainty -hold 0.5 [all_clocks]\n# Provisional internal')
for corner in ('tt_025C_3v30','ff_n40C_3v60','ss_n40C_3v00','ss_125C_3v00'):
 header=f'''read_liberty /pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__{corner}.lib
read_db /out/digital.odb
set_wire_rc -signal -layer Metal3
set_wire_rc -clock -layer Metal4
estimate_parasitics -placement
'''
 script=out/(corner+'.tcl');script.write_text(header+body)
 with (out/(corner+'.log')).open('w') as log:subprocess.run(['openroad','-no_init','-exit',str(script)],stdout=log,stderr=subprocess.STDOUT,check=True)
