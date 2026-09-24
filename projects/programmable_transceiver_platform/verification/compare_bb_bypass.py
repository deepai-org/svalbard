#!/usr/bin/env python3
"""Compare connected bypass after both complete matched zero/tone analyses exist."""
import hashlib,json
import numpy as np
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main(*, level10=False):
 records=[];provenance={}
 names=('bb-connected-bypass','bb-connected-level10') if level10 else ('bb-connected-settling','bb-connected-bypass')
 for name in names:
  ap=P/'evidence'/(name+'.json');fp=P/'evidence'/(name+'-conversion.json')
  audit=json.loads(ap.read_text());fit=json.loads(fp.read_text())
  assert audit['completed'] and fit['completed'] and fit['audit_sha256']==sha(ap)
  work=R/'scratch'/('transceiver-'+name)
  for c in audit['provenance']['cases']:
   for ext,h in c['artifacts_sha256'].items():assert sha(work/(c['name']+ext))==h
  records.append((audit,fit,work));provenance[name]=dict(audit_sha256=sha(ap),analysis_sha256=sha(fp))
 b,c=records;assert b[0]['provenance']['source_sha256_before']==c[0]['provenance']['source_sha256_before']
 rows=[]
 for case in ('zero','tone'):
  d=(c[2]/(case+'.spice')).read_text()
  if level10:
   if case=='tone':
    assert d.count('VRF RFS 0 SIN(0 0.01 2.51542263g)')==1
    d=d.replace('VRF RFS 0 SIN(0 0.01 2.51542263g)','VRF RFS 0 SIN(0 0.001 2.51542263g)')
  else:
   for n in (256,128,64):
    line=f'XCSB{n} LS 0 pt_ref_reservoir_{n}\n';assert d.count(line)==1;d=d.replace(line,'')
  assert d==(b[2]/(case+'.spice')).read_text()
  def select(record,window):
   return next(f for x in record[1]['cases'] if x['name']==case for f in x['fits'] if f['window_ns']==window and f['lo_harmonic_fit_order']==8)
  old=select(b,[240,400]);new=select(c,[240,400]);early=select(c,[240,320]);late=select(c,[320,400])
  row=dict(name=case,baseline=old,candidate=new)
  # Bias/headroom and power must accompany gain; compare identical late windows.
  physical=[]
  for record in (b,c):
   path=record[2]/(case+'.dat')
   with path.open() as stream:header=stream.readline().lower().split()
   raw=np.loadtxt(path,skiprows=1);w=raw[(raw[:,0]>=240e-9)&(raw[:,0]<=400e-9)];t=w[:,0]
   def mean(n):return float(np.trapezoid(w[:,header.index(n)],t)/(t[-1]-t[0]))
   powers={n:-3.3*mean('i('+n+')') for n in ('vlna','vbuf','vpll','vbb')}
   physical.append(dict(source_power_w=powers,accounted_supply_power_w=sum(powers.values()),
    rf_mean_v=mean('v(rf)'),source_mean_v=mean('v(ls)'),
    selected_finger_minimum_vds_margin_v=float(np.min(w[:,header.index('@m.xlna.x1.m0[vds]')]-w[:,header.index('@m.xlna.x1.m0[vdsat]')])),
    filter_i_common_mode_v=(mean('v(fip)')+mean('v(fin)'))/2,
    filter_q_common_mode_v=(mean('v(fqp)')+mean('v(fqn)'))/2))
  row['physical_baseline'],row['physical_candidate']=physical
  row['accounted_supply_power_change_w']=physical[1]['accounted_supply_power_w']-physical[0]['accounted_supply_power_w']
  if case=='tone':
   if level10:
    row['normalized_filter_gain_ratio']={q:new[f'filter_{q}_gain_from_source']/old[f'filter_{q}_gain_from_source'] for q in ('i','q')}
    row['normalized_gain_change_db']={q:float(20*np.log10(z)) for q,z in row['normalized_filter_gain_ratio'].items()}
   else:
    row['filter_gain_ratio']={q:new[f'filter_{q}_peak_v']/old[f'filter_{q}_peak_v'] for q in ('i','q')}
   row['late_window_amplitude_fraction_change']={q:late[f'filter_{q}_peak_v']/early[f'filter_{q}_peak_v']-1 for q in ('i','q')}
   row['relative_phase_change_deg']=new['filter_q_phase_deg']-old['filter_q_phase_deg']
  rows.append(row)
 out=dict(completed=True,provenance=provenance,cases=rows,limitations=[('Two nominal single-tone amplitudes; no1dB compression point, two-tone intercept, intrinsic noise or EVM claim.' if level10 else 'Nominal deterministic connected conversion; no intrinsic noise or EVM claim.'),'Seeded/prebiased history, ideal biases/supplies and no ADC; MIM bank has no extracted routing.','No requirement-derived gain/settling/linearity acceptance limit assigned by this comparison.'])
 (P/f'evidence/bb-{"level10" if level10 else "bypass"}-comparison.json').write_text(json.dumps(out,indent=2)+'\n');print('comparison complete')

if __name__ == '__main__':
 main()
