#!/usr/bin/env python3
"""Supply droop and analog residue, not only signed comparator decisions."""
import hashlib,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3];P=ROOT/'projects/programmable_transceiver_platform';W=ROOT/'scratch/transceiver-adc-cdac-supply';B=ROOT/'scratch/transceiver-adc-cdac-small-driver'
r=json.loads((W/'result.json').read_text());base=(B/'code127.spice').read_text()
assert hashlib.sha256(base.encode()).hexdigest()==r['baseline_deck_sha256']
for path,digest in r['source_sha256'].items():
 actual=P/'analog'/path.removeprefix('/screen/') if path.startswith('/screen/') else ROOT/'ip/blocks/analog/wifi_80211b'/path.removeprefix('/wifi/')
 assert hashlib.sha256(actual.read_bytes()).hexdigest()==digest
assert len(r['cases'])==6
for c in r['cases']:
 name=c['name'];R=c['resistance_ohm'];C=c['capacitance_pf']
 for suffix,digest in c['artifacts_sha256'].items():assert hashlib.sha256((W/(name+suffix)).read_bytes()).hexdigest()==digest
 expected=base.replace('VDRV VDRV 0 3.3',f'VDRV DRVSRC 0 3.3\nRDRV DRVSRC VDRV {R}\nCDRV VDRV 0 {C}p').replace('/work/code127.dat',f'/work/{name}.dat').replace('v(B7B)\n','v(B7B) v(VDRV)\n')
 assert (W/(name+'.spice')).read_text()==expected
 a=np.loadtxt(W/(name+'.dat'),skiprows=1);assert a.shape[1]==28 and np.isfinite(a).all() and a[-1,0]>=31e-9
 def win(lo,hi):return a[(a[:,0]>=lo*1e-9)&(a[:,0]<=hi*1e-9)]
 def diff(w):return float(np.mean(w[:,1]-w[:,2]))
 initial=diff(win(11,11.8));late=win(10.2,30.5)
 c['step_gain_ratio']=(diff(win(15,15.8))-initial)/(-2/256)
 c['return_error_uv']=(diff(win(25,25.8))-initial)*1e6
 c['driver_rail_range_v']=[float(late[:,27].min()),float(late[:,27].max())]
 c['peak_upstream_supply_current_ma']=float(np.max(-late[:,10])*1e3)
 c['upstream_source_energy_pj']=float(-3.3*np.trapezoid(late[:,10],late[:,0])*1e12)
 loss=R*np.trapezoid(late[:,10]**2,late[:,0])
 stored=.5*C*1e-12*(late[-1,27]**2-late[0,27]**2)
 c['inferred_driver_energy_pj']=c['upstream_source_energy_pj']-float((loss+stored)*1e12)
 c['decisions']=[]
 for edge,sign in ((16,-1),(26,1)):
  w=win(edge+1.9,edge+2.3);hi,lo=(3,4) if sign>0 else (4,3)
  c['decisions'].append(dict(edge_ns=edge,correct_rails=bool(w[:,hi].min()>2.97 and w[:,lo].max()<.33)))
r['supply_network_only_change_checked']=True;r['coexistence_qualified']=False
(P/'evidence/adc-cdac-supply-screen.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps([{k:v for k,v in c.items() if k!='artifacts_sha256'} for c in r['cases']],indent=2))
