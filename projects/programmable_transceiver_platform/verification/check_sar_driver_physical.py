"""Matched amplitude comparison; no scoring of incomplete simulation output."""
import argparse,hashlib,json,math
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
ap=argparse.ArgumentParser();group=ap.add_mutually_exclusive_group();group.add_argument('--reservoir-double',action='store_true');group.add_argument('--compensation',action='store_true');args=ap.parse_args()
comparison_mode=args.reservoir_double or args.compensation
parent_path=P/'evidence/sar-driver-physical.json'
parent=json.loads(parent_path.read_text()) if comparison_mode else None
if parent:assert parent['completed']
rows=[]
cases=[('sar-driver-reservoir-400',.4),('sar-driver-reservoir-100',.1)] if args.reservoir_double else [('sar-driver-physical-400',.4),('sar-driver-physical-100',.1),('sar-physical-control-100',.1)]
if args.compensation:cases=[('sar-reference-cc-half',.4),('sar-reference-cc-double',.4)]
for name,amplitude in cases:
 B=R/('scratch/transceiver-'+name+'-prepared');W=R/('scratch/transceiver-'+name);m=json.loads((B/'manifest.json').read_text());assert sha(B/'baseline.spice')==m['artifacts_sha256']['baseline.spice']
 s=(B/'baseline.spice').read_text();clamps='VCLH VH 0 2.15\nVCLL VL 0 1.15\n'
 assert 'VCLH ' not in s and 'VCLL ' not in s
 if args.compensation:
  assert sha(parent_path)==m['source_evidence_sha256']
  baseline=R/'scratch/transceiver-sar-driver-physical-400-prepared'
  assert sha(baseline/'manifest.json')==m['baseline_preparation_sha256']
  pair=P/'analog/reference/adc_reference_pair.spice'
  assert sha(pair)==m['pair_source_sha256']
  original=pair.read_text().rstrip();value=m['compensation_parameter']
  assert value in ('0.5p','2p') and original.count(' S=4')==2
  changed=original.replace(' S=4',' S=4 CC='+value)
  assert changed.replace(' CC='+value,'')==original
  assert s.count(changed)==1
  assert s.replace(changed,'.include /screen/reference/adc_reference_pair.spice')==(baseline/'baseline.spice').read_text()
 elif args.reservoir_double:
  assert sha(parent_path)==m['source_evidence_sha256']
  baseline=R/('scratch/transceiver-'+m['physical_source']+'-prepared')
  assert sha(baseline/'manifest.json')==m['baseline_preparation_sha256']
  extra='XHR_EXTRA VH 0 pt_ref_reservoir_2048\nXLR_EXTRA VL 0 pt_ref_reservoir_2048\n'
  assert s.count(extra)==1 and s.replace(extra,'')==(baseline/'baseline.spice').read_text()
 else:
  assert s.replace('.control',clamps+'.control')==(R/('scratch/transceiver-'+m['clamped_source']+'-prepared/baseline.spice')).read_text()
 row=dict(name=name,amplitude_v=amplitude,completed=False,status='pending',preparation_sha256=sha(B/'manifest.json'))
 if (W/'result.json').exists():
  r=json.loads((W/'result.json').read_text());assert r['sources_before']==r['sources_after'] and sha(W/'baseline.spice')==sha(B/'baseline.spice')
  for ext,d in r['artifacts_sha256'].items():assert sha(W/('baseline'+ext))==d
  errors=[l for l in (W/'baseline.log').read_text().splitlines() if any(k in l.lower() for k in ('warning','error','aborted','timestep too small'))]
  row.update(status='terminal',returncode=r['returncode'],timed_out=r['timed_out'],errors=errors)
  if r['returncode']==0 and not r['timed_out'] and not errors:
   with (W/'baseline.dat').open() as f:h=f.readline().lower().split()
   a=np.loadtxt(W/'baseline.dat',skiprows=1);t=a[:,0];assert len(h)==a.shape[1] and np.isfinite(a).all() and np.all(np.diff(t)>0) and t[-1]>=209.9e-9-1e-20
   def at(n,ns):return float(np.interp(ns*1e-9,t,a[:,h.index('v('+n+')')]))
   frames=[]
   for hold,target in [(70,amplitude),(120,-amplitude),(170,amplitude)]:
    bits=[at('d'+str(k),hold+39) for k in range(8)];valid=all(v<.33 or v>2.97 for v in bits);code=sum(int(v>1.65)*2**k for k,v in enumerate(bits));ideal=math.floor(128-128*target)
    points=[dict(offset_ns=dt,driver_error_v=at('ip',hold+dt)-at('in',hold+dt)-target,held_error_v=at('hp',hold+dt)-at('hn',hold+dt)-target) for dt in (0,.1,.5)]
    decisions=[]
    for j in range(8):
     q=at('qp',hold+2.4+5*j)-at('qn',hold+2.4+5*j);res=at('hp',hold+.5+5*j)-at('hn',hold+.5+5*j)
     decisions.append(dict(bit=7-j,preclock_residue_v=res,reference_span_v=at('vh',hold+.5+5*j)-at('vl',hold+.5+5*j),full_swing=bool(abs(q)>2.97),polarity_agrees=bool(np.sign(q)==np.sign(res))))
    mask=(t>=hold*1e-9)&(t<=(hold+39)*1e-9);span=a[:,h.index('v(vh)')]-a[:,h.index('v(vl)')]
    frames.append(dict(max_span_error_v=float(np.max(abs(span[mask]-1))),hold_ns=hold,final_code=code,final_bits_valid=valid,ideal_source_code=ideal,code_error=code-ideal,acquisition=points,decisions=decisions))
   row.update(completed=True,frames=frames,waveform_sha256=sha(W/'baseline.dat'),result_sha256=sha(W/'result.json'))
 rows.append(row)
if not comparison_mode:
 cell=(P/'analog/adc/sample_driver_headroom.spice').read_text().replace('RC X Z 100','RC X Z 2k').rstrip()
 for label,source in [('100',R/'scratch/transceiver-sar-physical-control-100-prepared/baseline.spice'),('400',R/'scratch/transceiver-adc-sar8-reference-reservoir/typical_first1.spice')]:
  s=(R/f'scratch/transceiver-sar-driver-physical-{label}-prepared/baseline.spice').read_text();assert s.count(cell)==1
  restored=s.replace(cell,'.include /screen/adc/sample_driver_headroom.spice')
  expected=source.read_text().replace('/work/typical_first1.dat','/work/baseline.dat')
  assert restored==expected
out=dict(completed=all(r['completed'] for r in rows),adopted=False,cases=rows,limitations=['Physical reference drivers with ideal targets/bias and phase clocks; two amplitudes do not qualify a transfer curve.','Correct selected final codes can coexist with offset, settling and input-history errors.'])
if comparison_mode:
 out['baseline_sha256']=sha(parent_path)
 for row in rows:
  source_name='sar-driver-physical-400' if args.compensation else row['name'].replace('reservoir','physical')
  base=next(c for c in parent['cases'] if c['name']==source_name)
  row['baseline_frames']=base['frames']
  if row['completed']:
   row['comparison']=[dict(hold_ns=f['hold_ns'],
    candidate_code_error=f['code_error'],baseline_code_error=b['code_error'],
    candidate_min_abs_decision_v=min(abs(x['preclock_residue_v']) for x in f['decisions']),
    baseline_min_abs_decision_v=min(abs(x['preclock_residue_v']) for x in b['decisions']),
    candidate_peak_span_error_v=f['max_span_error_v'],baseline_peak_span_error_v=b['max_span_error_v'])
    for f,b in zip(row['frames'],base['frames'])]
(P/('evidence/sar-reference-compensation.json' if args.compensation else 'evidence/sar-driver-reservoir.json' if args.reservoir_double else 'evidence/sar-driver-physical.json')).write_text(json.dumps(out,indent=2)+'\n')
for r in rows:print(r['name'],r['status'],[f['final_code'] for f in r.get('frames',[])])
