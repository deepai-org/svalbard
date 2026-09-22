#!/usr/bin/env python3
"""Check exact reference-network substitutions and report both favorable/adverse cases."""
import hashlib,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3];P=ROOT/'projects/programmable_transceiver_platform';W=ROOT/'scratch/transceiver-adc-cdac-reference';B=ROOT/'scratch/transceiver-adc-cdac-scaled'
r=json.loads((W/'result.json').read_text());base=(B/'code127_a1.spice').read_text()
assert hashlib.sha256(base.encode()).hexdigest()==r['baseline_deck_sha256']
for path,digest in r['source_sha256'].items():
 actual=P/'analog'/path.removeprefix('/screen/') if path.startswith('/screen/') else ROOT/'ip/blocks/analog/wifi_80211b'/path.removeprefix('/wifi/')
 assert hashlib.sha256(actual.read_bytes()).hexdigest()==digest
assert len(r['cases'])==9
for c in r['cases']:
 name=c['name'];R=c['reference_resistance_ohm'];C=c['reference_capacitance_pf']
 for suffix,digest in c['artifacts_sha256'].items():assert hashlib.sha256((W/(name+suffix)).read_bytes()).hexdigest()==digest
 expected=base.replace('RHR HR VH 10\n',f'RHR HR VH {R}\n').replace('RLR LR VL 10\n',f'RLR LR VL {R}\n').replace('CHR VH 0 10p\n',f'CHR VH 0 {C}p\n').replace('CLR VL 0 10p\n',f'CLR VL 0 {C}p\n').replace('/work/code127_a1.dat',f'/work/{name}.dat')
 assert (W/(name+'.spice')).read_text()==expected
 a=np.loadtxt(W/(name+'.dat'),skiprows=1);assert a.shape[1]==10 and np.isfinite(a).all() and a[-1,0]>=31e-9
 def window(lo,hi):return a[(a[:,0]>=lo*1e-9)&(a[:,0]<=hi*1e-9)]
 def diff(w):return float(np.mean(w[:,1]-w[:,2]))
 initial=diff(window(11,11.8));before=window(15,15.8);returned=window(25,25.8);late=window(10.2,30.5)
 c['predecision_step_v']=diff(before)-initial
 c['step_gain_ratio']=c['predecision_step_v']/(-2/256)
 c['return_error_before_second_decision_uv']=(diff(returned)-initial)*1e6
 c['peak_high_reference_error_mv']=float(np.max(np.abs(late[:,6]-2.15))*1e3)
 c['peak_low_reference_error_mv']=float(np.max(np.abs(late[:,7]-1.15))*1e3)
 c['predecision_reference_span_error_mv']=float(np.max(np.abs(before[:,6]-before[:,7]-1))*1e3)
 c['peak_reference_source_current_ma']=[float(np.max(np.abs(late[:,col]))*1e3) for col in (8,9)]
 c['decisions']=[]
 for edge,sign in ((16,-1),(26,1)):
  w=window(edge+1.9,edge+2.3);hi,lo=(3,4) if sign>0 else (4,3)
  c['decisions'].append(dict(edge_ns=edge,correct_rails=bool(w[:,hi].min()>2.97 and w[:,lo].max()<.33)))
 if R==10 and C==10:
  baseline=np.loadtxt(B/'code127_a1.dat',skiprows=1)
  assert a.shape==baseline.shape and np.allclose(a,baseline,rtol=1e-8,atol=1e-10),'Unchanged fixture did not reproduce baseline'
r['network_only_change_checked']=True;r['baseline_reproduced']=True;r['adc_accuracy_established']=False
(P/'evidence/adc-cdac-reference-screen.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps([{k:v for k,v in c.items() if k!='artifacts_sha256'} for c in r['cases']],indent=2))
