"""Extended actual loop transient; seeded acquisition screen, not lock qualification."""
import hashlib,json,subprocess
from pathlib import Path
import numpy as np
from closed_loop_screen import closed_loop_deck, measure_loop_windows
def main(variant='extended'):
 assert variant in ('extended','settling','gear')
 long=variant!='extended'
 stop_ns=3201 if long else 1201
 status={'extended':'extended_split_bias_loop_not_lock_qualification',
         'settling':'settling_split_bias_loop_not_lock_qualification',
         'gear':'gear2_settling_loop_numerical_crosscheck_not_lock_qualification'}[variant]
 O=Path('/work');base=Path('/chain/chain.spice').read_text()
 d=closed_loop_deck(base,split=True)
 # Retain only observed vectors to bound memory; circuit and timestep unchanged.
 saved='v(XRX.CP) v(XRX.CN) '+ ' '.join(f'v(Q{i}{leg})' for i in range(1,8) for leg in ('P','N'))+' v(FB) v(XRX.GATE) i(VDIV) v(UP) v(DN) v(CTRL) v(XFILT.Z) i(VSENSE) v(REF)'
 assert d.count('tran 2p 321n 0 2p uic')==1
 d=d.replace('tran 2p 321n 0 2p uic', 'save '+saved+f'\ntran 2p {stop_ns}n 0 2p uic')
 if variant=='gear':d=d.replace('.control', '.options method=gear maxord=2\n.control')
 p=O/'closed.spice';p.write_text(d)
 with (O/'closed.log').open('w') as log:subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=14400 if long else 5400)
 a=np.loadtxt(O/'closed.dat',skiprows=1);assert a.shape[1]==18 and np.isfinite(a).all() and a[-1,0]>(3200e-9 if long else 1200e-9)
 windows=((100,200),(220,320),(500,600),(800,900),(1100,1200))
 if long:windows+=((2000,2100),(3000,3100))
 rows=measure_loop_windows(a,windows)
 r=dict(status=status,windows=rows,artifacts_sha256={s:hashlib.sha256((O/('closed'+s)).read_bytes()).hexdigest() for s in ('.spice','.dat','.log')},limitations=[f'{stop_ns}ns with precharged filter, seeded VCO and prebiased LNA; no cold startup.', 'Finite seeded nominal record, no qualified lock/acquisition/stability or phase-noise claim.', 'Actual divide128/PFD/pump/filter/VCO, but ideal external bias sources/reference/sampling clocks.', 'Filter values are preliminary; no PVT/mismatch or physical parasitics.'])
 if variant=='gear':r['limitations'].append('Gear2 integration differs from aborted original run; numerical damping requires explicit comparison and does not prove physical stability.')
 (O/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))

if __name__ == '__main__':
 main()
