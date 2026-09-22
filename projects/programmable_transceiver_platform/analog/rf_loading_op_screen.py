#!/usr/bin/env python3
"""Frozen-switch bias/loading diagnostic, not conversion gain or periodic noise."""
import hashlib,json,re,subprocess
from pathlib import Path
import numpy as np
O=Path('/work');base=Path('/reference/a0.001.spice').read_text();rows=[]
for attached in (True,False):
 for state,p,n in [('one_on',3.3,0),('both_off',0,0),('both_on',3.3,3.3)]:
  name=f'{"filter" if attached else "bare"}_{state}'
  d=base[:base.index('.control')]
  d=re.sub(r'^VTESTLO .*$',f'VTESTLO TESTLO 0 {p}',d,flags=re.M)
  d=re.sub(r'^VTESTLOB .*$',f'VTESTLOB TESTLOB 0 {n}',d,flags=re.M)
  d=re.sub(r'^VRF .*$', 'VRF RF_SRC 0 DC 0 AC 1',d,flags=re.M)
  if not attached:d=d.replace('XF IP INN FP FN','XF DUMMY_P DUMMY_N FP FN')+'\nVDP DUMMY_P 0 1.177\nVDN DUMMY_N 0 1.177\n'
  d+=f'''.control
set wr_singlescale
set wr_vecnames
set numdgt=15
op
print v(GATE) v(DRAIN) v(SOURCE) v(IP) v(INN) v(XF.GP) v(XF.GN)
ac lin 2 2.5g 2.51g
wrdata /work/{name}.dat v(GATE) v(DRAIN) v(IP) v(INN)
.endc
.end
'''
  path=O/(name+'.spice');path.write_text(d)
  with (O/(name+'.log')).open('w') as log:subprocess.run(['ngspice','-b',str(path)],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90)
  text=(O/(name+'.log')).read_text();op={k:float(v) for k,v in re.findall(r'^(v\([^\n=]+\))\s*=\s*([-+\d.eE]+)',text,re.M)}
  assert len(op)==7,(name,op)
  a=np.atleast_2d(np.loadtxt(O/(name+'.dat'),skiprows=1));assert a.shape[1]==9 and a[0,0]==2.5e9 and np.isfinite(a).all()
  gains={node:float(abs(complex(a[0,col],a[0,col+1]))) for node,col in [('gate',1),('drain',3),('ip',5),('inn',7)]}
  row=dict(filter_attached=attached,state=state,op_v=op,rf_voltage_gains=gains,artifacts_sha256={s:hashlib.sha256((O/(name+s)).read_bytes()).hexdigest() for s in ('.spice','.dat','.log')});rows.append(row);print(json.dumps(row),flush=True)
r=dict(status='frozen_switch_dc_ac_diagnostic_not_conversion_gain',cases=rows,limitations=['LO frozen at extreme states; no periodically varying operating point or conversion gain.', 'Filter-disconnected case retains filter on ideal dummy inputs; IF 1kohm/1pF loads remain.', 'No phase noise, mismatch, PEX, package or ADC qualification.'])
(O/'result.json').write_text(json.dumps(r,indent=2)+'\n')
