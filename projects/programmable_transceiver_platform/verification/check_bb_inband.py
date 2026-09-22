"""Completion and finite-record conversion diagnostic for actual in-band receiver."""
import hashlib,json
from pathlib import Path
import numpy as np
from rf_tone_fit import fit
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-bb-inband';B=R/'scratch/transceiver-bb-connected-bypass'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
# Exercise the reused weighted fitter at the new two-cycle window length.
t=np.linspace(400e-9,800e-9,20001);freq=[5e6,2.4954222935e9,2.5004222935e9]
y=.8+.01*(t-t.mean())/(t[-1]-t[0])+.003*np.cos(2*np.pi*freq[0]*t)+.004*np.sin(2*np.pi*freq[0]*t)+.02*np.cos(2*np.pi*freq[1]*t)
z,res=fit(t,y,freq);assert abs(z-(.003-.004j))<1e-12 and res<1e-12
record=W/'result.json' if (W/'result.json').exists() else W/'progress.json'
r=json.loads(record.read_text()) if record.exists() else None
if r:assert r['sources_before']==r['sources_after']
rows=[]
for name in ('tone','zero'):
 row=dict(name=name,status='pending',completed=False);rows.append(row)
 if r is None or not any(c['name']==name for c in r['cases']):continue
 c=next(c for c in r['cases'] if c['name']==name);m=json.loads((W/(name+'-manifest.json')).read_text())
 assert m['sources_before']==r['sources_before']
 for ext,h in c['artifacts_sha256'].items():assert sha(W/(name+ext))==h
 assert sha(B/(name+'.spice'))==m['parent_deck_sha256']
 d=(W/(name+'.spice')).read_text()
 assert d.replace(m['new_source'],m['old_source']).replace('tran 2p 1201n 0 2p uic','tran 2p 401n 0 2p uic')==(B/(name+'.spice')).read_text()
 log=(W/(name+'.log')).read_text().lower();errors=[x for x in log.splitlines() if any(k in x for k in ('warning','error','aborted'))]
 row.update(status='terminal',returncode=c['returncode'],timed_out=c['timed_out'],errors=errors,artifacts_sha256=c['artifacts_sha256'])
 if c['returncode']!=0 or c['timed_out'] or errors:continue
 with (W/(name+'.dat')).open() as f:h=f.readline().lower().split()
 expected=next(x for x in d.splitlines() if x.startswith('wrdata ')).lower().split()[2:]
 assert h==['time']+expected
 a=np.loadtxt(W/(name+'.dat'),skiprows=1);assert a.shape[1]==len(h) and np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
 row['actual_stop_ns']=float(a[-1,0]*1e9)
 if a[-1,0]+1e-21<1201e-9:continue
 row.update(completed=True,fits=[])
 for lo,hi in m['intended_fit_windows_ns']:
  q=a[(a[:,0]>=lo*1e-9)&(a[:,0]<=hi*1e-9)];t=q[:,0];v=lambda n:q[:,h.index('v('+n+')')]
  osc=v('p')-v('n');k=np.flatnonzero((osc[:-1]<0)&(osc[1:]>=0));assert len(k)>100
  edges=t[k]-osc[k]*np.diff(t)[k]/np.diff(osc)[k];flo=float((len(edges)-1)/(edges[-1]-edges[0]));fif=m['rf_hz']-flo;assert 0<fif<10e6
  for order in (4,8):
   freqs=[fif]+[n*flo for n in range(1,order+1)]+[m['rf_hz'],m['rf_hz']+flo]
   zi,ri=fit(t,v('fip')-v('fin'),freqs);zq,rq=fit(t,v('fqp')-v('fqn'),freqs)
   row['fits'].append(dict(window_ns=[lo,hi],lo_hz=flo,if_hz=fif,if_cycles=float((t[-1]-t[0])*fif),harmonic_order=order,
    i_peak_v=float(abs(zi)),q_peak_v=float(abs(zq)),i_residual_rms_v=ri,q_residual_rms_v=rq,
    q_over_i=float(abs(zq/zi)) if name=='tone' and abs(zi)>0 else None,
    q_phase_deg=float(np.angle(zq/zi,deg=True)) if name=='tone' and abs(zi)>0 else None))
out=dict(completed=all(c['completed'] for c in rows),cases=rows,synthetic_fitter_check=True,
 limitations=['Two-cycle window fits require comparison across windows/orders and matched zero case; no automatic quality threshold.',
 'Residual is not intrinsic noise; no ADC, autonomous PLL, compression or ENOB qualification.',
 'Partial matrix remains incomplete even if tone case has measurements.'])
(P/'evidence/bb-inband.json').write_text(json.dumps(out,indent=2)+'\n');print([(c['name'],c['status'],c['completed']) for c in rows])
