#!/usr/bin/env python3
"""Check observation-only replay and report raw device quantities cautiously."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-tx-device-op-dc';B=R/'scratch/transceiver-tx-common-mode-dc'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):
 with p.open() as f:h=f.readline().lower().split()
 a=np.loadtxt(p,skiprows=1);assert a.shape==(256,len(h)) and np.isfinite(a).all() and np.array_equal(a[:,0],np.arange(256))
 return h,a
m=json.loads((W/'manifest.json').read_text());r=json.loads((W/'result.json').read_text());assert r['source_sha256_before']==r['source_sha256_after']==m['source_sha256_before']
tails=[f'xd.xcl{i}.xtail' for i in range(4)]+[f'xd.xch{i}.xtail' for i in range(1,16)];switches=['xm.xp.xp0','xm.xp.xp1','xm.xn.xn0','xm.xn.xn1'];params=['vds','vdsat','vgs','vth','id'];vectors=[f'@m.{d}.m0[{p}]' for d in tails+switches for p in params]
assert m['vectors']==vectors and m['tails']==tails and m['switches']==switches
assert [c['name'] for c in r['cases']]==['lower','baseline','upper']
rows=[]
for c in r['cases']:
 name=c['name'];src=B/(name+'.spice');assert sha(src)==c['baseline_deck_sha256']
 expected=src.read_text().replace('dc VCODE 0 255 1','save all '+' '.join(vectors)+'\ndc VCODE 0 255 1').replace('.endc','wrdata /work/'+name+'_devices.dat '+' '.join(vectors)+'\n.endc')
 assert (W/(name+'.spice')).read_text()==expected and sha(W/(name+'.spice'))==c['deck_sha256_before']
 for n,h in c['artifacts_sha256'].items():assert sha(W/n)==h
 log=(W/(name+'.log')).read_text().lower();assert c['returncode']==0 and 'aborted' not in log and 'no such' not in log
 hb,ab=read(B/(name+'.dat'));h,a=read(W/(name+'.dat'));assert h==hb and np.array_equal(a,ab)
 hd,ad=read(W/(name+'_devices.dat'));assert hd[1:]==vectors
 def q(d,p):return ad[:,1+vectors.index(f'@m.{d}.m0[{p}]')]
 margin=np.concatenate([q(d,'vds')-q(d,'vdsat') for d in tails])
 current=sum(q(d,'id') for d in tails)
 devices={}
 for d in switches:
  devices[d]={p:[float(q(d,p).min()),float(q(d,p).max())] for p in params}
  devices[d]['reported_vgs_minus_vth_range_v']=[float((q(d,'vgs')-q(d,'vth')).min()),float((q(d,'vgs')-q(d,'vth')).max())]
 rows.append(dict(name=name,original_waveforms_bit_identical=True,all_19_tail_min_vds_minus_vdsat_v=float(margin.min()),summed_tail_current_a_range=[float(current.min()),float(current.max())],switch_raw_reported_parameters=devices))
out=dict(status='completed_observation_only',cases=rows,provenance=r,limitations=['Static typical and ideal biases only; no RF switching, noise, mismatch or temperature coverage.', 'Mixer fingers can reverse conduction across code; raw model vgs/vth/id are reported without assuming forward-conduction conventions apply universally.', 'Positive DAC tail VDS-VDSAT supports saturation in these sweeps, not precision or dynamic compliance.', 'Only four representative conducting mixer fingers are probed; no off-state isolation qualification.'])
(P/'evidence/tx-device-op-dc.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(rows,indent=2))
