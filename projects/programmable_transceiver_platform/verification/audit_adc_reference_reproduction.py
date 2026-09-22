#!/usr/bin/env python3
"""Scope probe replay validity without changing the failed all-vector gate."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';E=P/'evidence/adc-reference-current-replay.json';W=R/'scratch/transceiver-adc-reference-current';B=R/'scratch/transceiver-adc-shared-iq-damping2k'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
e=json.loads(E.read_text());assert e['completed'] and e['same_time_grid']
for root,artifacts in [(W,e['provenance']['artifacts_sha256']),(B,e['baseline_artifacts_sha256'])]:
 for ext,h in artifacts.items():assert sha(root/('frames'+ext))==h
with (B/'frames.dat').open() as f:h=f.readline().lower().split()
a=np.loadtxt(W/'frames.dat',skiprows=1);b=np.loadtxt(B/'frames.dat',skiprows=1);assert np.array_equal(a[:,0],b[:,0]);t=a[:,0]
failures=[]
for i,name in enumerate(h[1:],1):
 delta=abs(a[:,i]-b[:,i]);limit=e['current_tolerance_a'] if name.startswith('i(') else e['voltage_tolerance_v']
 if delta.max()>limit:
  k=int(delta.argmax());failures.append(dict(node=name,time_ns=t[k]*1e9,max_error=float(delta[k]),replay_value=float(a[k,i]),baseline_value=float(b[k,i])))
# Retain the original voltage tolerance for all observed analog signal/reference nodes.
analog=['v(hp)','v(hn)','v(q_hp)','v(q_hn)','v(ip)','v(in)','v(vh)','v(vl)','v(xd.xp7.bot)','v(xd.xn7.bot)','v(xref.xhigh.x)','v(xref.xlow.x)']
analog_errors={n:float(abs(a[:,h.index(n)]-b[:,h.index(n)]).max()) for n in analog}
current_errors={n:e['original_vector_max_errors'][n] for n in h if n.startswith('i(')}
code_checks=[]
for hold in (70,120,170):
 mask=(t>=(hold+39.3)*1e-9)&(t<=(hold+39.7)*1e-9)
 for prefix in ('','q_'):
  ix=[h.index('v('+prefix+'d'+str(i)+')') for i in range(8)]
  av=a[mask][:,ix];bv=b[mask][:,ix];assert np.all((av<.33)|(av>2.97)) and np.all((bv<.33)|(bv>2.97))
  assert np.array_equal(av>1.65,bv>1.65)
  code_checks.append(dict(hold_ns=hold,channel=prefix or 'i',codes=np.unique((av>1.65).astype(int)@2**np.arange(8)).tolist()))
edges=[]
for n in ['v(keepp)','v(keepn)']+['v('+p+'d'+str(i)+')' for p in ('','q_') for i in range(8)]:
 ix=h.index(n)
 for rising in (True,False):
  ts=[]
  for arr in (a,b):
   y=arr[:,ix];k=np.flatnonzero(((y[:-1]<1.65)&(y[1:]>=1.65)) if rising else ((y[:-1]>1.65)&(y[1:]<=1.65)))
   ts.append(t[k]+(1.65-y[k])*np.diff(t)[k]/np.diff(y)[k])
  assert len(ts[0])==len(ts[1]);edges.append(dict(node=n,rising=rising,count=len(ts[0]),max_time_difference_ps=float(abs(ts[0]-ts[1]).max()*1e12) if len(ts[0]) else 0))
valid=max(analog_errors.values())<=e['voltage_tolerance_v'] and max(current_errors[n] for n in ['i(vrefsup)','i(vbuf)'])<=e['current_tolerance_a'] and max(x['max_time_difference_ps'] for x in edges)<1
out=dict(status='scoped_reference_replay_audit',original_global_gate=e['reproduction_verified'],scoped_current_diagnostic_valid=bool(valid),replay_evidence_sha256=sha(E),failed_global_vectors=failures,analog_max_errors_v=analog_errors,current_max_errors_a=current_errors,capture_checks=code_checks,logic_edge_checks=edges,scope='Original10uV/10nA tolerances retained for listed analog nodes and reference/input-buffer supply currents; digital supply currents explicitly excluded from scoped equivalence; identical captured codes; logic crossing changes below1ps diagnostic limit (100x smaller than tested100ps sampler shifts).',limitations=['Scoped diagnostic permission only; not bit-identical replay or ADC qualification. Digital switching supply currents differ and cannot be treated as matched power evidence.','1ps criterion is an explicitly added diagnostic criterion after locating transition-local differences, not original global acceptance.','New branch-current accuracy still needs timestep/convention checks before precision claims.'])
(P/'evidence/adc-reference-reproduction-scope.json').write_text(json.dumps(out,indent=2)+'\n');print(valid,'analog_max',max(analog_errors.values()),'edge_ps',max(x['max_time_difference_ps'] for x in edges))
