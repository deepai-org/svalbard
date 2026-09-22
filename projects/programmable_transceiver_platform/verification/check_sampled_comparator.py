#!/usr/bin/env python3
"""Verify controlled clock substitution and measure held-sample disturbance."""
import hashlib,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3];P=ROOT/'projects/programmable_transceiver_platform';W=ROOT/'scratch/transceiver-adc-sampled-comparator'
r=json.loads((W/'result.json').read_text())
for path,digest in r['source_sha256'].items():
 actual=P/'analog'/path.removeprefix('/screen/') if path.startswith('/screen/') else ROOT/'ip/blocks/analog/wifi_80211b'/path.removeprefix('/wifi/')
 assert hashlib.sha256(actual.read_bytes()).hexdigest()==digest
assert len(r['cases'])==24
pairs=[]
for c in r['cases']:
 for suffix,digest in c['artifacts_sha256'].items():assert hashlib.sha256((W/(c['name']+suffix)).read_bytes()).hexdigest()==digest
 if not c['active']:continue
 control=next(x for x in r['cases'] if not x['active'] and all(x[k]==c[k] for k in ('common_mode_v','hold_cap_pf','sign')))
 active_deck=(W/(c['name']+'.spice')).read_text()
 idle_deck=(W/(control['name']+'.spice')).read_text()
 assert active_deck.replace('VC CLK 0 PULSE(0 3.3 12n 100p 100p 2.4n 20n)','VC CLK 0 0').replace(c['name'],control['name'])==idle_deck
 a=np.loadtxt(W/(c['name']+'.dat'),skiprows=1);b=np.loadtxt(W/(control['name']+'.dat'),skiprows=1)
 assert a.shape[1]==b.shape[1]==9 and np.isfinite(a).all() and np.isfinite(b).all()
 t=a[:,0];delta=a[:,1]-a[:,2];cm=(a[:,1]+a[:,2])/2
 bd=np.interp(t,b[:,0],b[:,1]-b[:,2]);bc=np.interp(t,b[:,0],(b[:,1]+b[:,2])/2)
 before=(t>=11e-9)&(t<=11.8e-9);after=(t>=12e-9)&(t<=19.5e-9);end=(t>=19e-9)&(t<=19.5e-9)
 assert np.max(np.abs(delta[before]-bd[before]))<1e-7
 assert np.all(a[after,6]<.001) and np.all(a[after,7]>3.299),'Sampler must be off during comparison'
 w=a[(t>=13.9e-9)&(t<=14.3e-9)];hi,lo=(3,4) if c['sign']>0 else (4,3)
 assert c['correct_rails']==bool(w[:,hi].min()>2.97 and w[:,lo].max()<.33)
 pairs.append(dict(common_mode_v=c['common_mode_v'],hold_cap_pf=c['hold_cap_pf'],sign=c['sign'],correct_rails=c['correct_rails'],sampler_turnoff_differential_error_uv=float((np.mean(bd[before])-c['sign']*.001)*1e6),peak_comparator_differential_disturbance_uv=float(np.max(np.abs(delta[after]-bd[after]))*1e6),peak_comparator_common_mode_disturbance_mv=float(np.max(np.abs(cm[after]-bc[after]))*1e3),post_reset_differential_disturbance_uv=float(np.mean(delta[end]-bd[end])*1e6)))
r['paired_metrics']=pairs;r['clock_only_difference_checked']=True;r['active_cases_passing_rails']=sum(x['correct_rails'] for x in pairs);r['adc_precision_established']=False
(P/'evidence/adc-sampled-comparator-screen.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(pairs,indent=2))
