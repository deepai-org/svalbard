#!/usr/bin/env python3
"""Check connected elaboration without calling startup or conversion qualified."""
import argparse,hashlib,json
ap=argparse.ArgumentParser();ap.add_argument("--dedup",action="store_true");args=ap.parse_args()
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';name='rx-adc-preflight-dedup' if args.dedup else 'rx-adc-preflight';W=R/'scratch'/('transceiver-'+name)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((W/'manifest.json').read_text());r=json.loads((W/'result.json').read_text())
assert r['sources_before']==r['sources_after']==m['sources_before']
assert sha(W/'connected.spice')==m['deck_sha256']
assert sha(R/'scratch/transceiver-rx-adc-connected-prepared/connected.spice')==m['parent_sha256']
for ext,h in r['artifacts_sha256'].items():assert sha(W/('connected'+ext))==h
with (W/'connected.dat').open() as f:header=f.readline().lower().split()
a=np.loadtxt(W/'connected.dat',skiprows=1)
assert a.shape[1]==len(header) and np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
deck=(W/'connected.spice').read_text();wr=next(l for l in deck.splitlines() if l.startswith('wrdata '))
assert header==['time']+[n.lower() for n in wr.split()[2:]]
log=(W/'connected.log').read_text();warnings=[l.strip() for l in log.splitlines() if 'warning' in l.lower() or 'ignored' in l.lower()]
complete=r['returncode']==0 and not r['timed_out'] and a[-1,0]+1e-21>=1e-9 and 'aborted' not in log.lower()
out=dict(completed=bool(complete),rows=len(a),columns=len(header),actual_stop_s=float(a[-1,0]),artifact_sha256=r['artifacts_sha256'],warnings=warnings,final_bias_v={n:float(a[-1,header.index('v(xadc.'+n+')')]) for n in ['bn','bp','q_bn','q_bp','rbn','rbp']},limitations=['One nanosecond only verifies elaboration and finite exports, not settled bias or circuit quality.','Duplicate subcircuit warnings require source/include review before a full run.','Seeded UIC, ideal supplies/bias and clocks remain; no autonomous or cold-start qualification.'])
if args.dedup:
 base=R/'scratch/transceiver-rx-adc-preflight'
 old=json.loads((base/'result.json').read_text())
 for ext,h in old['artifacts_sha256'].items():assert sha(base/('connected'+ext))==h
 assert deck.replace('.include /screen/adc/sar_track_mask_strong.spice', '.include /screen/reference/reservoir_mim.spice\n.include /screen/adc/sar_track_mask_strong.spice')==(base/'connected.spice').read_text()
 b=np.loadtxt(base/'connected.dat',skiprows=1)
 with (base/'connected.dat').open() as f:assert header==f.readline().lower().split()
 out['identical_original_waveform']=bool(np.array_equal(a,b))
 out['duplicate_warnings_removed']=not warnings
 out['limitations'][1]='Include cleanup only; unchanged1ns waveform does not qualify longer startup or conversion.'
(P/'evidence'/(name+'.json')).write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
