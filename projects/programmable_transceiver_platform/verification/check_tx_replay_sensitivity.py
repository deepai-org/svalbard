#!/usr/bin/env python3
import hashlib,json,re
from pathlib import Path
import numpy as np
from tx_cycle_metrics import cycle_amplitude
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-tx-replay-sensitivity';B=R/'scratch/transceiver-tx-measured-lo-replay'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
if not (W/'result.json').exists():print('Pending sensitivity cases');raise SystemExit(0)
m=json.loads((W/'manifest.json').read_text());r=json.loads((W/'result.json').read_text());assert m['source_sha256_before']==r['source_sha256_before']==r['source_sha256_after'];src=B/'replay.spice';assert sha(src)==m['baseline_deck_sha256'];original=src.read_text()
def sources(d):return [re.search('^'+n+r' '+node+r' 0 PWL\(([^\n]+)\)$',d,re.M) for n,node in [('VLO','LOIN'),('VLOB','LOBIN')]]
def parse(match):return np.asarray([float(x) for x in match.group(1).split()]).reshape(-1,2)
old=sources(original);a,b=map(parse,old);assert np.array_equal(a[:,0],b[:,0]);cm=(a[:,1]+b[:,1])/2;diff=(a[:,1]-b[:,1])/2
assert [(c['name'],c['offset_v'],c['differential_scale']) for c in r['cases']]==[('cm_minus',-.15,1),('cm_plus',.15,1),('swing_low',0,.75),('swing_high',0,1.25)];rows=[]
for c in r['cases']:
 name=c['name'];d=(W/(name+'.spice')).read_text();assert sha(W/(name+'.spice'))==c['deck_sha256_before'];changed=sources(d)
 for idx,(new,prior) in enumerate(zip(changed,old)):
  pairs=parse(new);assert np.array_equal(pairs[:,0],a[:,0]);expected=cm+c['offset_v']+(1 if idx==0 else -1)*c['differential_scale']*diff;assert np.allclose(pairs[:,1],expected,atol=1e-14,rtol=0);d=d.replace(new.group(0),prior.group(0))
 assert d.replace(f'/work/{name}.dat','/work/replay.dat')==original
 for ext,h in c['artifacts_sha256'].items():assert sha(W/(name+ext))==h
 assert c['returncode']==0 and not c['timed_out'] and 'aborted' not in (W/(name+'.log')).read_text().lower()
 with (W/(name+'.dat')).open() as f:h=f.readline().lower().split()
 assert h==['time']+next(l for l in d.splitlines() if l.startswith('save ')).lower().split()[1:]
 ar=np.loadtxt(W/(name+'.dat'),skiprows=1);assert ar.shape[1]==len(h) and np.isfinite(ar).all() and np.all(np.diff(ar[:,0])>0) and ar[-1,0]>=10e-9
 ar=ar[ar[:,0]>=6e-9];t=ar[:,0]
 def v(k):return ar[:,h.index(k)]
 y=v('v(lo)');ix=np.where((y[:-1]<1.65)&(y[1:]>=1.65))[0];cross=t[ix]+(t[ix+1]-t[ix])*(1.65-y[ix])/(y[ix+1]-y[ix]);amps=cycle_amplitude(t,v('v(rfp)')-v('v(rfn)'),cross)
 rows.append(dict(name=name,complete_cycles=len(amps),rf_fundamental_peak_range_v=[min(amps),max(amps)] if amps else None,lo_range_v=[float(y.min()),float(y.max())],buffer_power_w=float(-3.3*np.trapezoid(v('i(vlobuf)'),t)/(t[-1]-t[0]))))
out=dict(status='completed_clock_input_sensitivity',cases=rows,provenance=r,limitations=['Stimulus transformations are diagnostic, not realizable circuit changes or uncertainty bounds.', 'Differential scaling preserves waveform shape but changes slew too; no amplitude-only attribution.', 'No loading feedback, autonomous noise/modulation or physical restorer fix demonstrated.'])
(P/'evidence/tx-replay-sensitivity.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(rows,indent=2))
