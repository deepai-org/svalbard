#!/usr/bin/env python3
import hashlib,json,re
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-dac-dynamic';B=R/'scratch/transceiver-dac-loaded-dc'
manifest=json.loads((W/'manifest.json').read_text());source=B/'v2.15_r100.spice';assert hashlib.sha256(source.read_bytes()).hexdigest()==manifest['baseline_deck_sha256']
for path,digest in manifest['source_sha256_before'].items():
 if path.startswith('/screen/'):assert hashlib.sha256((P/'analog'/path.removeprefix('/screen/')).read_bytes()).hexdigest()==digest
original=source.read_text().split('.control')[0];stripped=re.sub(r'^(?:B\d+|BB\d+) .+\n','',original,flags=re.M).replace('VCODE CODE 0 0\n','')
static=np.loadtxt(B/'v2.15_r100.dat',skiprows=1);targets={code:float(static[code,2]-static[code,1]) for code in (127,128)};lsb=float((static[-1,2]-static[-1,1]-static[0,2]+static[0,1])/255)
rows=[];pending=[]
for units in (32,128):
 for skew in (-.2,0,.2):
  name=f'c{units}_skew{skew:g}';file=W/(name+'.dat');log=W/(name+'.log')
  if not file.exists() or not log.exists() or 'Note: Simulation executed from .control section' not in log.read_text():pending.append(name);continue
  d=(W/(name+'.spice')).read_text();assert d.split('.include /screen/adc/code_driver_small.spice')[0]==stripped
  assert f'XCP OP 0 pt_ref_reservoir_{units}\nXCN ON 0 pt_ref_reservoir_{units}' in d and 'tran 5p 79.9n 0 5p' in d
  a=np.loadtxt(file,skiprows=1);assert a.shape[1]==29 and np.isfinite(a).all() and a[-1,0]>=79.9e-9
  header=file.read_text().splitlines()[0].split();assert header[1:5]==['v(OP)','v(ON)','v(BN)','i(VDRV)']
  t=a[:,0]*1e9;v=a[:,2]-a[:,1]
  for bit in range(8):
   assert header[5+2*bit:7+2*bit]==[f'v(B{bit})',f'v(B{bit}B)'] and header[21+bit]==f'v(D{bit})'
   shift=skew if bit==7 else 0;first=3.3 if bit<7 else 0;other=3.3-first
   points=[0,30+shift,30.1+shift,55+shift,55.1+shift];values=[first,first,other,other,first]
   assert np.max(abs(a[:,21+bit]-np.interp(t,points,values)))<1e-6
   assert f'XDRV{bit} D{bit} B{bit} B{bit}B VDRV 0 pt_adc_code_small_driver WEIGHT={2**bit}' in d
   for lo,hi,code in ((20,25,127),(45,50,128),(70,75,127)):
    w=a[(t>=lo)&(t<=hi)];expected=(code>>bit)&1
    assert np.all(w[:,5+2*bit]>(2.97)) if expected else np.all(w[:,5+2*bit]<.33)
    assert np.all(w[:,6+2*bit]<.33) if expected else np.all(w[:,6+2*bit]>2.97)
  transitions=[]
  for edge,old,new in ((30,127,128),(55,128,127)):
   w=(t>=edge-.5)&(t<=edge+10);tw=a[w,0];ideal=np.where(t[w]<edge+.05,targets[old],targets[new]);error=v[w]-ideal
   late=(t>=edge+15)&(t<=edge+20);post=(t>=edge+.3)&(t<=edge+20);bad=np.flatnonzero(post&(abs(v-targets[new])>lsb/2))
   settled=not np.any(abs(v[late]-targets[new])>lsb/2)
   transitions.append(dict(edge_ns=edge,old_code=old,new_code=new,peak_error_mv=float(np.max(abs(error))*1e3),signed_error_area_mv_ns=float(np.trapezoid(error,tw)*1e12),absolute_error_area_mv_ns=float(np.trapezoid(abs(error),tw)*1e12),late_mean_error_mv=float((v[late].mean()-targets[new])*1e3),late_half_lsb_band_pass=bool(settled),last_half_lsb_violation_after_edge_ns=float(t[bad[-1]]-edge) if len(bad) else None))
  rows.append(dict(name=name,load_units=units,msb_skew_ns=skew,transitions=transitions,driver_peak_current_ma=float(np.max(-a[:,4])*1e3),artifacts_sha256={ext:hashlib.sha256((W/(name+ext)).read_bytes()).hexdigest() for ext in ('.spice','.dat','.log')}))
complete=(W/'result.json').exists()
if complete:
 full=json.loads((W/'result.json').read_text());assert full['source_sha256_before']==full['source_sha256_after']==manifest['source_sha256_before'];assert all(c['returncode']==0 for c in full['cases'])
r=dict(status='major_carry_dynamic_audited' if complete and not pending else 'partial_major_carry_dynamic_audit',cases=rows,pending=pending,dc_targets_v=targets,endpoint_lsb_v=lsb,qualified_radio_DAC=False,limitations=['Half-LSB is an exploratory8-bit settling diagnostic, not an allocated RF/SFDR requirement.', 'Ideal transition used for error area occurs at command midpoint; area depends on this convention.', '5ps timestep, finite selected transitions and load/skew scenarios; no noise/mismatch or numerical convergence qualification.'])
(P/'evidence/current-dac-dynamic-screen.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(dict(completed=[dict(name=c['name'],peak_error_mv=[x['peak_error_mv'] for x in c['transitions']],settling_ns=[x['last_half_lsb_violation_after_edge_ns'] for x in c['transitions']]) for c in rows],pending=pending),indent=2))
