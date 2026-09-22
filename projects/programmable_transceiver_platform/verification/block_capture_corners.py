"""Container runner: fixed nominally mapped fixture, five available 3.3V-class corners."""
import hashlib,json,pathlib,subprocess
base=pathlib.Path('/pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib')
src=pathlib.Path('/src/verification');out=pathlib.Path('/out')
nom=str(base/'gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.lib')
hashes={}
for corner in ('tt_025C_3v30','ff_n40C_3v60','ff_125C_3v60','ss_n40C_3v00','ss_125C_3v00'):
 lib=base/('gf180mcu_fd_sc_mcu7t5v0__'+corner+'.lib')
 hashes[corner]=hashlib.sha256(lib.read_bytes()).hexdigest()
 for kind,template in [('setup','block_capture_timing.tcl'),('hold','block_capture_hold.tcl')]:
  script=(src/template).read_text().replace(nom,str(lib)).replace('/out/mapped.v','/mapped/mapped.v').replace('/out/capture-pins.tcl','/mapped/capture-pins.tcl')
  path=out/(corner+'-'+kind+'.tcl');path.write_text(script)
  with (out/(corner+'-'+kind+'.log')).open('w') as log:
   subprocess.run(['sta','-exit',str(path)],stdout=log,stderr=subprocess.STDOUT,check=True)
(out/'libraries.json').write_text(json.dumps(hashes,indent=2)+'\n')
