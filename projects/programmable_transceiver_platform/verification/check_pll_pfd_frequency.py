#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];W=ROOT/'scratch/transceiver-pll-pfd-frequency';r=json.loads((W/'result.json').read_text())
for c in r['cases']:
 name=f"period{c['feedback_period_ns']}"
 for s,h in c['artifacts_sha256'].items():assert hashlib.sha256((W/(name+s)).read_bytes()).hexdigest()==h
 c['reset_reentry_pass']=c['reset_output_max_v']<.1
 period=c['feedback_period_ns']
 events=sorted([(40+40*n,'ref') for n in range(31)]+[(40+period*n,'fb') for n in range(35)]+[(600.1,'reset'),(640.1,'release')])
 up=dn=0;reset=False;prev=0;area=[0.,0.]
 for t,event in events:
  dt=max(0,min(t,1200)-max(prev,700));area[0]+=dt*up;area[1]+=dt*dn
  if event=='reset':reset=True;up=dn=0
  elif event=='release':reset=False
  elif not reset:
   if event=='ref':up=1
   else:dn=1
   if up and dn:up=dn=0
  prev=t
 c['ideal_event_net_area_s']=(area[0]-area[1])*1e-9
 c['event_reference_pass']=abs(c['up_minus_down_s']-c['ideal_event_net_area_s'])<1e-9
 c['frequency_direction_pass']=c['up_minus_down_s']*(c['feedback_period_ns']-40)>0
r['all_checks_pass']=all(c['reset_reentry_pass'] and c['frequency_direction_pass'] and c['event_reference_pass'] for c in r['cases'])
(ROOT/'projects/programmable_transceiver_platform/evidence/pll-pfd-frequency-screen.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r,indent=2))
assert r['all_checks_pass']
