import pathlib,subprocess,hashlib,json
out=pathlib.Path('/out');base=pathlib.Path('/pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib')
src=pathlib.Path('/src/verification/block_rx_prefix_timing.tcl').read_text()
hashes={}
for corner in ('tt_025C_3v30','ff_n40C_3v60','ff_125C_3v60','ss_n40C_3v00','ss_125C_3v00'):
 lib=base/('gf180mcu_fd_sc_mcu7t5v0__'+corner+'.lib');hashes[corner]=hashlib.sha256(lib.read_bytes()).hexdigest()
 script=out/(corner+'.tcl');script.write_text(src.replace('tt_025C_3v30',corner).replace('/out/mapped.v','/mapped/mapped.v'))
 with (out/(corner+'.log')).open('w') as f:subprocess.run(['sta','-exit',str(script)],stdout=f,stderr=subprocess.STDOUT,check=True)
(out/'libraries.json').write_text(json.dumps(hashes,indent=2)+'\n')
