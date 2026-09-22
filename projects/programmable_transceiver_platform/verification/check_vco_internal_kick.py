"""Ordinal crossing comparison for deterministic signed output charge pulses."""
import argparse,hashlib,json,re
ap=argparse.ArgumentParser();ap.add_argument("--fine",action="store_true");args=ap.parse_args()
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-vco-internal-kick-v2';B=R/'scratch/transceiver-vco-split-tuning/v1.08.spice'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((W/'manifest.json').read_text());assert sha(B)==m['baseline_deck_sha256'] and m['pulse_nodes']==['XRX.XVCO.N0P','XRX.XVCO.N0N']
terminal=(W/'result.json').exists();record=W/('result.json' if terminal else 'progress.json');r=json.loads(record.read_text()) if record.exists() else {'cases':[]}
if terminal:assert r['source_sha256_before']==r['source_sha256_after']==m['source_sha256_before']
rows=[];edges={}
for name,amplitude in [('quiet',0),('positive',1e-4),('negative',-1e-4)]:
 row=dict(name=name,status='pending',completed=False);rows.append(row)
 if not any(c['name']==name for c in r['cases']):continue
 c=next(c for c in r['cases'] if c['name']==name)
 for ext,h in c['artifacts_sha256'].items():assert sha(W/(name+ext))==h
 d=(W/(name+'.spice')).read_text();assert ('tran .5p 41n 0 .5p uic' if args.fine else 'tran 2p 41n 0 2p uic') in d
 pulse=f'IKICK XRX.XVCO.N0P XRX.XVCO.N0N PWL(0n 0 20n 0 20.001n {amplitude} 20.011n {amplitude} 20.012n 0)\n'
 assert d.count(pulse)==1 and d.replace(pulse,'').replace(f'/work/{name}.dat','/work/v1.08.dat').replace('tran .5p 41n 0 .5p uic','tran 2p 41n 0 2p uic')==B.read_text()
 assert 'let cml=v(XRX.CP)-v(XRX.CN)' in d
 log=(W/(name+'.log')).read_text().lower();errors=[x for x in log.splitlines() if any(k in x for k in ('warning','error','aborted'))]
 row.update(status='terminal',returncode=c['returncode'],timed_out=c['timed_out'],errors=errors,artifacts_sha256=c['artifacts_sha256'])
 if c['returncode']!=0 or c['timed_out'] or errors:continue
 with (W/(name+'.dat')).open() as f:h=f.readline().lower().split()
 a=np.loadtxt(W/(name+'.dat'),skiprows=1);assert a.shape[1]==len(h) and np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
 row['actual_stop_ns']=float(a[-1,0]*1e9)
 if a[-1,0]+1e-21<41e-9:continue
 t=a[:,0];y=a[:,h.index('cml')];k=np.flatnonzero((y[:-1]<0)&(y[1:]>=0));e=t[k]-y[k]*np.diff(t)[k]/np.diff(y)[k]
 edges[name]=e;row.update(completed=True,rising_edges=len(e),pulse_charge_c=amplitude*11e-12)
if 'quiet' in edges:
 for row in rows:
  name=row['name']
  if name not in edges:continue
  base=edges['quiet'];candidate=edges[name];row['same_edge_count']=len(base)==len(candidate)
  if len(base)!=len(candidate):continue
  delta=candidate-base;row['windows']=[]
  for lo,hi in [(10,19),(20,21),(21,25),(30,40)]:
   mask=(base>=lo*1e-9)&(base<=hi*1e-9);assert mask.any()
   row['windows'].append(dict(window_ns=[lo,hi],edge_count=int(mask.sum()),mean_displacement_ps=float(delta[mask].mean()*1e12),max_abs_displacement_ps=float(abs(delta[mask]).max()*1e12)))
out=dict(completed=terminal and all(x['completed'] for x in rows),cases=rows,source_hashes_final_verified=terminal,
 limitations=['One injection phase/amplitude at one internal differential stage; not a full phase-sensitivity function or intrinsic noise.',
 'Maximum step is0.5ps in fine mode,2ps otherwise; compare matched response before quantitative interpretation.',
 'Ordinal edges are never rematched; unequal count prevents displacement comparison.',
 'Fixed ideal control/bias, seeded open-loop oscillator with historical RF/divider load; not autonomous PLL qualification.'])
(P/'evidence'/'vco-internal-kick.json').write_text(json.dumps(out,indent=2)+'\n');print([(x['name'],x['status'],x.get('windows')) for x in rows])
