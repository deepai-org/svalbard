import pathlib,subprocess
src=pathlib.Path('/src/verification');out=pathlib.Path('/out')
for corner in ('tt_025C_3v30','ff_n40C_3v60','ss_125C_3v00'):
 body=(src/'block_elastic_timing.tcl').read_text().split('create_clock',1)[1]
 body='create_clock'+body
 body=body.replace('source /out/pins.tcl','set_propagated_clock [all_clocks]\nset_clock_uncertainty -hold 0.5 [get_clocks rd_clk]\nsource /mapped/pins.tcl')
 header=f'''read_liberty /pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__{corner}.lib
read_db /out/digital.odb
set_wire_rc -signal -layer Metal3
set_wire_rc -clock -layer Metal4
estimate_parasitics -placement
'''
 script=out/(corner+'.tcl');script.write_text(header+body)
 with (out/(corner+'.log')).open('w') as log:
  subprocess.run(['openroad','-no_init','-exit',str(script)],stdout=log,stderr=subprocess.STDOUT,check=True)
