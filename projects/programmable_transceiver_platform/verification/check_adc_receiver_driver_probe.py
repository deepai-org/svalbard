#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-adc-receiver-driver-probe';B=R/'scratch/transceiver-adc-shared-iq-receiver-cm'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((W/'manifest.json').read_text());assert sha(B/'frames.spice')==m['baseline_deck_sha256'];d=(W/'frames.spice').read_text();assert sha(W/'frames.spice')==m['deck_sha256_before']
rev=d.replace(m['save_addition'],'');rev='\n'.join(line.removesuffix(' '+m['extra_probes']) if line.startswith('wrdata ') else line for line in rev.split('\n'));assert rev==(B/'frames.spice').read_text()
out=dict(status='pending',completed=False,limitations=['Observation-only replay; device id is not automatically instantaneous terminal current.','Original waveforms must reproduce before using probes to explain prior behavior.'])
if (W/'result.json').exists():
 r=json.loads((W/'result.json').read_text());assert r['source_sha256_before']==r['source_sha256_after']==m['source_sha256_before'];out['provenance']=r
 for e,h in r['artifacts_sha256'].items():assert sha(W/('frames'+e))==h
 out['status']='terminal'
 if (W/'frames.dat').exists():
  with (W/'frames.dat').open() as f:header=f.readline().lower().split()
  with (B/'frames.dat').open() as f:bh=f.readline().lower().split()
  assert header==bh+m['extra_probes'].lower().split()
  a=np.loadtxt(W/'frames.dat',skiprows=1);b=np.loadtxt(B/'frames.dat',skiprows=1);assert np.isfinite(a).all() and np.all(np.diff(a[:,0])>=0)
  out['completed']=bool(r['returncode']==0 and not r['timed_out'] and 'aborted' not in (W/'frames.log').read_text().lower() and a[-1,0]+1e-21>=209.9e-9)
  out['original_vectors_bit_identical']=bool(a[:,:len(bh)].shape==b.shape and np.array_equal(a[:,:len(bh)],b));out['actual_stop_ns']=float(a[-1,0]*1e9)
(P/'evidence/adc-receiver-driver-probe.json').write_text(json.dumps(out,indent=2)+'\n');print(out['status'],out['completed'])
