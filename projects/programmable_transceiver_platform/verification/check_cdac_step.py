#!/usr/bin/env python3
"""Measure code response and return error, preserving failed nominal cases."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
args=argparse.ArgumentParser();args.add_argument('--scaled',action='store_true');args=args.parse_args()
ROOT=Path(__file__).resolve().parents[3];P=ROOT/'projects/programmable_transceiver_platform';tag='scaled' if args.scaled else 'step';W=ROOT/('scratch/transceiver-adc-cdac-'+tag)
r=json.loads((W/'result.json').read_text())
if args.scaled:
 source=(P/'analog/adc/cdac8_scaled.spice').read_text()
 assert 'w=2u l=.28u m={S}' in source and 'w=4u l=.28u m={S}' in source
 for bit in range(8):assert source.count(f'CVAL={{CU*{2**bit}}} SW={2**bit}\n')==2
 for c in r['cases']:
  original=(ROOT/'scratch/transceiver-adc-cdac-step'/(c['name']+'.spice')).read_text()
  updated=(W/(c['name']+'.spice')).read_text()
  assert updated.replace('cdac8_scaled.spice','cdac8.spice').replace('pt_cdac8_scaled','pt_cdac8')==original
 r['switch_scaling_only_substitution_checked']=True
for path,digest in r['source_sha256'].items():
 actual=P/'analog'/path.removeprefix('/screen/') if path.startswith('/screen/') else ROOT/'ip/blocks/analog/wifi_80211b'/path.removeprefix('/wifi/')
 assert hashlib.sha256(actual.read_bytes()).hexdigest()==digest
assert len(r['cases'])==8
for c in r['cases']:
 for suffix,digest in c['artifacts_sha256'].items():assert hashlib.sha256((W/(c['name']+suffix)).read_bytes()).hexdigest()==digest

def read(c):
 a=np.loadtxt(W/(c['name']+'.dat'),skiprows=1)
 assert a.shape[1]==10 and np.isfinite(a).all() and a[-1,0]>=31e-9
 return a

def window(a,lo,hi):return a[(a[:,0]>=lo*1e-9)&(a[:,0]<=hi*1e-9)]
def diffmean(a,lo,hi):
 w=window(a,lo,hi);return float(np.mean(w[:,1]-w[:,2]))
rows=[]
for c in r['cases']:
 if not c['active']:continue
 idle=next(x for x in r['cases'] if x['code']==c['code'] and not x['active'])
 ad=(W/(c['name']+'.spice')).read_text();bd=(W/(idle['name']+'.spice')).read_text()
 assert ad.replace('VC CLK 0 PULSE(0 3.3 16n 100p 100p 2.4n 10n)','VC CLK 0 0').replace(c['name'],idle['name'])==bd
 a,b=read(c),read(idle)
 initial=diffmean(b,11,11.8);stepped=diffmean(b,15,15.8);returned=diffmean(b,25,25.8)
 ideal_step=2*(c['code']-128)/256
 w=window(a,10.2,30.5)
 disturbance=(w[:,1]-w[:,2])-np.interp(w[:,0],b[:,0],b[:,1]-b[:,2])
 decisions=[]
 for edge,expected in ((16,np.sign(.001+ideal_step)),(26,1)):
  x=window(a,edge+1.9,edge+2.3);hi,lo=(3,4) if expected>0 else (4,3)
  decisions.append(dict(clock_edge_ns=edge,expected_ideal_input_sign=float(expected),correct_rails=bool(x[:,hi].min()>2.97 and x[:,lo].max()<.33),min_expected_high_v=float(x[:,hi].min()),max_expected_low_v=float(x[:,lo].max())))
 rows.append(dict(code=c['code'],initial_held_difference_v=initial,ideal_differential_step_v=ideal_step,measured_idle_step_v=stepped-initial,step_gain_ratio=(stepped-initial)/ideal_step,idle_code_return_error_uv=(returned-initial)*1e6,active_code_return_error_uv=(diffmean(a,25,25.8)-initial)*1e6,peak_comparator_differential_disturbance_mv=float(np.max(np.abs(disturbance))*1e3),reference_high_range_v=[float(w[:,6].min()),float(w[:,6].max())],reference_low_range_v=[float(w[:,7].min()),float(w[:,7].max())],decisions=decisions))
r['paired_metrics']=rows;r['clock_only_difference_checked']=True;r['adc_complete']=False
(P/('evidence/adc-cdac-'+tag+'-screen.json')).write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(rows,indent=2))
