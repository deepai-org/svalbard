"""Scope local AC evidence for independently biased second LO inverter."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-lo-interstage-ac';rows=[]
for name in ['baseline','isolated']:
 log=(W/(name+'.log')).read_text().lower();assert 'ngspice-46 done' in log and not any(x in log for x in ['warning','error','aborted'])
 a=np.loadtxt(W/(name+'.dat'),skiprows=1);assert a.shape==(81,9) and np.isfinite(a).all()
 gains={str(f):[float(np.interp(np.log(f),np.log(a[:,0]),abs(a[:,k]+1j*a[:,k+1]))) for k in [1,3,5,7]] for f in [19.53125e6,2.5e9]}
 rows.append(dict(name=name,gain_magnitude_in_mid_pre_out=gains,artifacts_sha256={ext:hashlib.sha256((W/(name+ext)).read_bytes()).hexdigest() for ext in ['.spice','.log','.dat']}))
report=dict(status='local_small_signal_topology_hypothesis',cases=rows,limitations=['50fF final load only; real mixer/filter loading and ring backloading absent.', 'Linearized around1.530318V equilibrium; large AC gains do not imply unclipped physical amplitudes.', 'Four PDK unit coupling capacitors and10kohm local feedback are exploratory choices.', 'No transient startup, phase noise, duty-cycle or autonomous-loop qualification.'])
(P/'evidence/lo-interstage-ac.json').write_text(json.dumps(report,indent=2)+'\n');print('Two AC fixtures complete; diagnostic scope only')
