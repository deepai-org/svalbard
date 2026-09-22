"""Render retained TX phase and training windows; requires NumPy and Matplotlib."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from chip_model import P
p=P/'evidence';rows=[]
fig,axes=plt.subplots(2,1,figsize=(10,6),constrained_layout=True)
for mode,ax in enumerate(axes):
 z=np.load(p/f'connected-tx-filter-quarter-250k-mode{mode}-traces.npz')
 t=z['time_s'];t=(t-t[0])*1e6;x=z['ideal_tx'];y=z['actual_tx'];ph=np.unwrap(np.angle(z['actual_rotation']*np.conj(z['ideal_rotation'])))
 ph-=np.mean(ph);n=len(t)//4
 ax.plot(t,ph,label='Actual LO phase relative to ideal carrier (mean removed)',lw=1)
 ax.axvspan(t[0],t[n],color='orange',alpha=.15,label='Existing gain-training window')
 ax.axvline(t[np.flatnonzero(abs(x)>1e-8)[0]],color='gray',ls=':',label='First nonzero TX envelope')
 ax.set(xlabel='Time after first host word (µs)',ylabel='Phase (rad)',title=f'Mode {mode}: retained quarter-fraction / 250 kHz trial')
 bins=[]
 for indices in np.array_split(np.arange(len(t)),8):
  a=x[indices];b=y[indices];power=np.vdot(a,a).real
  gain=np.vdot(a,b)/power if power else complex(float('nan'))
  bins.append(dict(start_us=float(t[indices[0]]),end_us=float(t[indices[-1]]),phase_mean_rad=float(ph[indices].mean()),signal_energy=float(power),gain_phase_rad=float(np.angle(gain))))
 rows.append(dict(mode=mode,bins=bins))
axes[0].legend(fontsize=8)
fig.savefig(p/'tx-startup-phase-windows.png',dpi=150)
(p/'tx-startup-phase-windows.json').write_text(json.dumps(dict(cases=rows,scope='Diagnostic visualization; original gate unchanged'),indent=2)+'\n')
print(json.dumps(rows,indent=2))
