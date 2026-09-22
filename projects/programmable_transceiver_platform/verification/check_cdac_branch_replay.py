#!/usr/bin/env python3
"""Validate branch probes, original behavior, and high-rail independent current sum."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-cdac-branch-replay';B=R/'scratch/transceiver-adc-reference-current'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((W/'manifest.json').read_text());assert sha(W/'frames.spice')==m['deck_sha256_before'] and sha(B/'frames.spice')==m['baseline_deck_sha256']
out=dict(status='pending',completed=False,analog_reproduction_verified=False)
if (W/'result.json').exists():
 r=json.loads((W/'result.json').read_text());assert r['source_sha256_before']==r['source_sha256_after']==m['source_sha256_before']
 br=json.loads((B/'result.json').read_text())
 for root,rec in [(W,r),(B,br)]:
  for ext,h in rec['artifacts_sha256'].items():assert sha(root/('frames'+ext))==h
 def read(p):
  with p.open() as f:h=f.readline().lower().split()
  a=np.loadtxt(p,skiprows=1);assert a.shape[1]==len(h) and np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
  return h,a
 h,a=read(W/'frames.dat');bh,b=read(B/'frames.dat');assert h==bh+[x.lower() for x in m['extra_probes']]
 t=a[:,0];done=r['returncode']==0 and not r['timed_out'] and t[-1]+1e-21>=209.9e-9 and 'aborted' not in (W/'frames.log').read_text().lower()
 out.update(status='terminal',completed=bool(done),provenance=r,baseline_artifacts_sha256=br['artifacts_sha256'])
 if done:
  same=np.array_equal(t,b[:,0]);errors={}
  for i,name in enumerate(bh[1:],1):errors[name]=float(abs(a[:,i]-(b[:,i] if same else np.interp(t,b[:,0],b[:,i]))).max())
  analog=['v(hp)','v(hn)','v(q_hp)','v(q_hn)','v(vh)','v(vl)','v(ip)','v(in)']
  out.update(same_time_grid=same,original_vector_max_errors=errors,analog_reproduction_verified=max(errors[n] for n in analog)<1e-5,analog_tolerance_v=1e-5)
  codes=[]
  for hold in (70,120,170):
   for prefix in ('','q_'):
    ix=[h.index(f'v({prefix}d{i})') for i in range(8)];mask=(t>=(hold+39.3)*1e-9)&(t<=(hold+39.7)*1e-9);bm=(b[:,0]>=(hold+39.3)*1e-9)&(b[:,0]<=(hold+39.7)*1e-9)
    av=a[mask][:,ix];bv=b[bm][:,ix];assert np.all((av<.33)|(av>2.97)) and np.all((bv<.33)|(bv>2.97))
    ac=np.unique((av>1.65).astype(int)@2**np.arange(8)).tolist();bc=np.unique((bv>1.65).astype(int)@2**np.arange(8)).tolist();codes.append(dict(hold_ns=hold,channel=prefix or 'i',candidate=ac,baseline=bc))
  out['codes']=codes;out['codes_match']=all(x['candidate']==x['baseline'] for x in codes)
  def v(n):return a[:,h.index(n)]
  balances={}
  for rail in ['h','l']:
   names=[f'i(v.{inst}.x{side}{bit}.x{rail}.vport)' for inst in ['xd','xq_d'] for side in ['p','n'] for bit in range(8)]
   summed=sum(v(n) for n in names);demand=v(f'i(vref{rail}_del)')-v(f'i(vref{rail}_res)');residual=demand-summed
   balances[rail]=dict(branches=len(names),max_residual_a=float(abs(residual).max()),signed_residual_charge_c=float(np.trapezoid(residual,t)),interpretation='Independent high-rail KCL closure' if rail=='h' else 'Includes four unsensed dummy-capacitor reference terminals; not a closed KCL test')
  out['rail_current_sums']=balances;out['high_rail_kcl_verified']=balances['h']['max_residual_a']<1e-9
out['limitations']=['Low-rail branch sum omits dummy capacitors; do not assign its residual to switch overlap.','Terminal currents include displacement; opposing signed rail currents alone do not prove conductive crossover.','Analog reproduction uses10uV diagnostic threshold, not whole-chip precision qualification.']
(P/'evidence/cdac-branch-replay.json').write_text(json.dumps(out,indent=2)+'\n');print(out['status'],out['completed'],out['analog_reproduction_verified'])
