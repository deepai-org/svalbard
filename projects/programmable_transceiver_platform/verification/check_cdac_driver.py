#!/usr/bin/env python3
"""Check transistor-driver substitution, loaded timing, residue and rail current."""
import argparse,hashlib,json,re
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3];P=ROOT/'projects/programmable_transceiver_platform';B=ROOT/'scratch/transceiver-adc-cdac-scaled'
parser=argparse.ArgumentParser();parser.add_argument('--small',action='store_true');args=parser.parse_args()
tag='small-driver' if args.small else 'driver';W=ROOT/('scratch/transceiver-adc-cdac-'+tag)
r=json.loads((W/'result.json').read_text())
if args.small:
 source=(P/'analog/adc/code_driver_small.spice').read_text()
 original=(P/'analog/adc/code_driver.spice').read_text()
 assert source.replace('pt_adc_drive_small_inv','pt_adc_drive_inv').replace('pt_adc_code_small_driver','pt_adc_code_driver').replace('w=1u','w=4u').replace('w=.5u','w=2u')==original
 r['quarter_width_driver_only_change_checked']=True
for path,digest in r['source_sha256'].items():
 actual=P/'analog'/path.removeprefix('/screen/') if path.startswith('/screen/') else ROOT/'ip/blocks/analog/wifi_80211b'/path.removeprefix('/wifi/')
 assert hashlib.sha256(actual.read_bytes()).hexdigest()==digest
assert len(r['cases'])==4
for c in r['cases']:
 name,code=c['name'],c['code'];base=(B/f'code{code}_a1.spice').read_text()
 assert hashlib.sha256(base.encode()).hexdigest()==c['baseline_deck_sha256']
 for suffix,digest in c['artifacts_sha256'].items():assert hashlib.sha256((W/(name+suffix)).read_bytes()).hexdigest()==digest
 d=(W/(name+'.spice')).read_text()
 if args.small:d=d.replace('code_driver_small.spice','code_driver.spice').replace('pt_adc_code_small_driver','pt_adc_code_driver')
 # Reverse driver additions and recover the exact original circuit/stimulus deck.
 for bit in range(8):
  assert f'XDRV{bit} D{bit} B{bit} B{bit}B VDRV 0 pt_adc_code_driver WEIGHT={2**bit}\n' in d
  d=d.replace(f'XDRV{bit} D{bit} B{bit} B{bit}B VDRV 0 pt_adc_code_driver WEIGHT={2**bit}\n','')
  command=re.search(rf'^VB{bit} B{bit} 0 .+$',base,re.M).group(0)
  complement=re.search(rf'^VB{bit}B B{bit}B 0 .+$',base,re.M).group(0)
  d=re.sub(rf'^VD{bit} D{bit} 0 .+$',command+'\n'+complement,d,flags=re.M)
 d=d.replace('.include /screen/adc/code_driver.spice\nVDRV VDRV 0 3.3\n','')
 d=d.replace(' i(VDRV) '+' '.join(f'v(B{i}) v(B{i}B)' for i in range(8)),'').replace(f'/work/{name}.dat',f'/work/code{code}_a1.dat')
 assert d==base
 a=np.loadtxt(W/(name+'.dat'),skiprows=1);assert a.shape[1]==27 and np.isfinite(a).all() and a[-1,0]>=31e-9
 def win(lo,hi):return a[(a[:,0]>=lo*1e-9)&(a[:,0]<=hi*1e-9)]
 def diff(w):return float(np.mean(w[:,1]-w[:,2]))
 initial=diff(win(11,11.8));pre=win(15,15.8);late=win(10.2,30.5)
 c['step_gain_ratio']=(diff(pre)-initial)/(2*(code-128)/256)
 c['return_error_uv']=(diff(win(25,25.8))-initial)*1e6
 c['peak_driver_supply_current_ma']=float(np.max(-late[:,10])*1e3)
 c['driver_energy_over_10p2_to_30p5ns_pj']=float(-3.3*np.trapezoid(late[:,10],late[:,0])*1e12)
 c['peak_high_reference_error_mv']=float(np.max(np.abs(late[:,6]-2.15))*1e3)
 c['peak_low_reference_error_mv']=float(np.max(np.abs(late[:,7]-1.15))*1e3)
 timing=[]
 for bit in range(8):
  if ((128>>bit)&1)==((code>>bit)&1):continue
  w=win(12,16)
  crossing=[]
  for col in (11+2*bit,12+2*bit):
   v=w[:,col]-1.65;i=np.flatnonzero(v[:-1]*v[1:]<0)
   assert len(i)>=1
   j=i[0];edge=w[j,0]-v[j]*(w[j+1,0]-w[j,0])/(v[j+1]-v[j]);crossing.append(float((edge-12.05e-9)*1e9))
  timing.append(dict(bit=bit,true_delay_ns=crossing[0],complement_delay_ns=crossing[1],complement_minus_true_ns=crossing[1]-crossing[0]))
 c['loaded_edge_delays']=timing;c['decisions']=[]
 for edge,sign in ((16,np.sign(.001+2*(code-128)/256)),(26,1)):
  w=win(edge+1.9,edge+2.3);hi,lo=(3,4) if sign>0 else (4,3)
  c['decisions'].append(dict(edge_ns=edge,correct_rails=bool(w[:,hi].min()>2.97 and w[:,lo].max()<.33)))
r['driver_only_substitution_checked']=True;r['sar_controller_complete']=False
(P/('evidence/adc-cdac-'+tag+'-screen.json')).write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps([{k:v for k,v in c.items() if k not in ('artifacts_sha256','baseline_deck_sha256')} for c in r['cases']],indent=2))
