#!/usr/bin/env python3
import hashlib,json,re
from pathlib import Path
import numpy as np
from tx_cycle_metrics import cycle_amplitude
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-tx-measured-lo-replay';B=R/'scratch/transceiver-tx-buffered-lo';M=R/'scratch/transceiver-tx-ring-settling'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
if not (W/'result.json').exists():print('Pending measured-waveform replay');raise SystemExit(0)
m=json.loads((W/'manifest.json').read_text());r=json.loads((W/'result.json').read_text());assert r['source_sha256_before']==r['source_sha256_after']==m['source_sha256_before'];assert sha(B/'nmos_c255.spice')==m['baseline_deck_sha256'] and sha(M/'settling.dat')==m['measured_wave_sha256']
with (M/'settling.dat').open() as f:hm=f.readline().lower().split()
am=np.loadtxt(M/'settling.dat',skiprows=1);t=np.r_[590e-9,am[(am[:,0]>590e-9)&(am[:,0]<600e-9),0],600e-9]
d=(W/'replay.spice').read_text();assert sha(W/'replay.spice')==m['deck_sha256_before']
for name,node,col,old in [('VLO','LOIN','v(loin)','PULSE(0 3.3 1n 20p 20p 180p 400p)'),('VLOB','LOBIN','v(lobin)','PULSE(3.3 0 1n 20p 20p 180p 400p)')]:
 match=re.search(r'^'+name+' '+node+r' 0 PWL\(([^\n]+)\)$',d,re.M);assert match
 pairs=np.asarray([float(x) for x in match.group(1).split()]).reshape(-1,2);assert len(pairs)==len(t)==m['samples']
 assert np.array_equal(pairs[:,0],t-590e-9) and np.allclose(pairs[:,1],np.interp(t,am[:,0],am[:,hm.index(col)]),rtol=0,atol=1e-14)
 d=d.replace(match.group(0),f'{name} {node} 0 {old}')
assert d.replace('/work/replay.dat','/work/nmos_c255.dat')==(B/'nmos_c255.spice').read_text()
for ext,h in r['artifacts_sha256'].items():assert sha(W/('replay'+ext))==h
assert r['returncode']==0 and not r['timed_out'] and 'aborted' not in (W/'replay.log').read_text().lower()
with (W/'replay.dat').open() as f:h=f.readline().lower().split()
a=np.loadtxt(W/'replay.dat',skiprows=1);assert a.shape[1]==len(h) and np.isfinite(a).all() and np.all(np.diff(a[:,0])>0) and a[-1,0]>=10e-9
a=a[a[:,0]>=6e-9];t=a[:,0]
def v(k):return a[:,h.index(k)]
y=v('v(lo)');ix=np.where((y[:-1]<1.65)&(y[1:]>=1.65))[0];cross=t[ix]+(t[ix+1]-t[ix])*(1.65-y[ix])/(y[ix+1]-y[ix]);amps=cycle_amplitude(t,v('v(rfp)')-v('v(rfn)'),cross)
out=dict(status='completed_measured_input_replay',complete_cycles=len(amps),rf_fundamental_peak_range_v=[min(amps),max(amps)],provenance=r,limitations=['Stiff measured-waveform sources remove bidirectional loading; this is diagnostic, not oscillator qualification.', 'OP-initialized downstream DAC differs from UIC connected startup; no noise or modulation claims.', 'Measured waveform includes amplitude, common mode and edge shape together; does not isolate their individual contributions.'])
(P/'evidence/tx-measured-lo-replay.json').write_text(json.dumps(out,indent=2)+'\n');print(out['rf_fundamental_peak_range_v'])
