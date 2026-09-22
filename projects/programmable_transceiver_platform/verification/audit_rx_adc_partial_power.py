"""Selected supply energy before the failed receiver's first conversion finishes."""
import hashlib,json,re
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
W=R/'scratch/transceiver-rx-adc-loading/loaded'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((W/'result.json').read_text())
assert r['returncode']!=0 and r['sources_before']==r['sources_after']
for ext,h in r['artifacts_sha256'].items():assert sha(W/('connected'+ext))==h
text=(W/'connected.spice').read_text()
with (W/'connected.dat').open() as f:header=f.readline().lower().split()
a=np.loadtxt(W/'connected.dat',skiprows=1);t=a[:,0]
assert a.shape[1]==len(header) and np.isfinite(a).all() and np.all(np.diff(t)>=0)
# Match each measured voltage source to its own hierarchical circuit.
contracts=[('pt_rx_loaded','xrx','vbb','baseband_filters'),
           ('pt_adc_pair_loaded','xadc','vbuf','four_sample_drivers'),
           ('pt_adc_pair_loaded','xadc','vrefsup','reference_pair')]
rails=[]
for cell,instance,source,label in contracts:
 body=re.search(r'(?ims)^\.subckt '+cell+r'\b.*?^\.ends[^\n]*',text).group()
 line=next(x for x in body.lower().splitlines() if x.startswith(source+' '))
 parts=line.split();assert len(parts)==4 and parts[2]=='0' and float(parts[3])==3.3
 name=f'i(v.{instance}.{source})';assert name in header
 rails.append((label,-3.3*a[:,header.index(name)]))
windows=[]
# Windows are diagnostic, chosen to separate tracking and early conversion.
for lo,hi in [(350,400),(420,450),(450,469),(470.2,478.3)]:
 lo*=1e-9;hi*=1e-9
 m=(t>=lo-3e-12)&(t<=hi+3e-12)
 tt=t[m];assert tt[0]<=lo and tt[-1]>=hi and np.all(np.diff(tt)>0)
 inside=(tt>lo)&(tt<hi);grid=np.r_[lo,tt[inside],hi]
 stats={};total=np.zeros_like(grid)
 for label,power in rails:
  yy=power[m];v=np.r_[np.interp(lo,tt,yy),yy[inside],np.interp(hi,tt,yy)]
  energy=float(np.trapezoid(v,grid));total+=v
  stats[label]=dict(mean_mw=energy/(hi-lo)*1e3,energy_pj=energy*1e12,
                   native_window_peak_mw=float(v.max()*1e3),minimum_mw=float(v.min()*1e3))
 windows.append(dict(window_ns=[lo*1e9,hi*1e9],rails=stats,
                     selected_rails_mean_mw=float(np.trapezoid(total,grid)/(hi-lo)*1e3)))
out=dict(status='partial_failed_run_selected_supply_energy',completed=False,
 artifacts_sha256=r['artifacts_sha256'],windows=windows,
 limitations=['Not whole-chip power or a guaranteed lower bound: other ideal sources can supply or absorb energy.',
 'Excludes LNA, oscillator, LO buffers, ADC logic/comparators/CDAC drivers, ideal controls and bias implementation.',
 'Early conversion window is incomplete; no repeated-conversion average or thermal/package qualification.',
 'Positive power is energy delivered by each measured supply, not independently measured heat.'])
(P/'evidence/rx-adc-partial-power.json').write_text(json.dumps(out,indent=2)+'\n')
for w in windows:print(w['window_ns'], {k:round(v['mean_mw'],4) for k,v in w['rails'].items()},round(w['selected_rails_mean_mw'],4))
