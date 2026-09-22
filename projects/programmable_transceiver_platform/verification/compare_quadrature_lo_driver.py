#!/usr/bin/env python3
"""Matched added-stage comparison; report costs without automatic adoption."""
import hashlib,json,math,sys
ACCOUPLED="--ac-coupled" in sys.argv
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(name):return json.loads((P/'evidence'/name).read_text())
base_stem='quadrature-lna-final' if ACCOUPLED else 'quadrature-lna'
new_stem='quadrature-lna-ac' if ACCOUPLED else 'quadrature-lna-final'
a=read(base_stem+'.json');b=read(new_stem+'.json');ca=read(base_stem+'-conversion.json');cb=read(new_stem+'-conversion.json')
out=dict(completed=False,status='pending',limitations=['One nominal seeded/prebiased RF tone; no broadband gain/noise/linearity or process qualification.','Added common inversion changes absolute conversion polarity; amplitude/relative-IQ comparisons do not imply preserved absolute phase.','Accounted supply power excludes ideal control/regeneration/common-mode/bias sources and other chip functions.'])
if all(x['completed'] for x in (a,b,ca,cb)):
 for audit,conversion,name in [(a,ca,base_stem+'.json'),(b,cb,new_stem+'.json')]:assert conversion['audit_sha256']==sha(P/'evidence'/name)
 sa=a['provenance']['source_sha256_before'];sb=b['provenance']['source_sha256_before'];assert all(sb[k]==v for k,v in sa.items());assert set(sb)-set(sa)==(set() if ACCOUPLED else {'/screen/quadrature/lo_final_stage.spice'})
 roots=[R/'scratch'/('transceiver-'+stem) for stem in (base_stem,new_stem)]
 for root,audit in zip(roots,(a,b)):
  for case in audit['provenance']['cases']:
   for ext,h in case['artifacts_sha256'].items():assert sha(root/(case['name']+ext))==h
 for name in ('zero','tone'):
  fine=(roots[1]/(name+'.spice')).read_text()
  if ACCOUPLED:
   fine=fine.replace('XAC RF MRFIN pt_ref_reservoir_256\n','').replace('XMI MRFIN OIP','XMI RF OIP').replace('XMQ MRFIN OQP','XMQ RF OQP').replace(' v(MRFIN)','')
  else:
   fine=fine.replace('.include /screen/quadrature/lo_final_stage.spice\n','')
   for node in ('IP','IN','QP','QN'):
    fine=fine.replace(f'XF{node} PRE{node} O{node} VDD 0 pt_lo_final_stage\n','').replace(f'XB{node} B{node} PRE{node} VDD 0 pt_lo_buffer',f'XB{node} B{node} O{node} VDD 0 pt_lo_buffer')
  assert fine==(roots[0]/(name+'.spice')).read_text()
 out.update(completed=True,status='terminal_comparison',windows=[])
 aa=next(c for c in ca['cases'] if c['name']=='tone')['fits'];bb=next(c for c in cb['cases'] if c['name']=='tone')['fits']
 for x,y in zip(aa,bb):
  assert (x['window_ns'],x['lo_harmonic_fit_order'])==(y['window_ns'],y['lo_harmonic_fit_order'])
  out['windows'].append(dict(window_ns=x['window_ns'],harmonic_fit_order=x['lo_harmonic_fit_order'],i_gain_ratio=y['i_peak_v']/x['i_peak_v'],q_gain_ratio=y['q_peak_v']/x['q_peak_v'],i_gain_improvement_db=20*math.log10(y['i_peak_v']/x['i_peak_v']),q_gain_improvement_db=20*math.log10(y['q_peak_v']/x['q_peak_v']),baseline_q_over_i=x['q_over_i'],candidate_q_over_i=y['q_over_i'],baseline_q_phase_deg=x['q_relative_phase_deg'],candidate_q_phase_deg=y['q_relative_phase_deg']))
 out['power']=[]
 for name in ('zero','tone'):
  x=next(c for c in a['cases'] if c['name']==name);y=next(c for c in b['cases'] if c['name']==name)
  powers=('buffer_supply_power_w','ring_supply_power_w','lna_supply_power_w')
  out['power'].append(dict(case=name,baseline={k:x[k] for k in powers},candidate={k:y[k] for k in powers},accounted_power_increase_w=sum(y[k]-x[k] for k in powers)))
if ACCOUPLED:out['limitations'][1]='AC coupling changes mixer operating point and loading; selected tone comparison cannot establish broadband matching or complete receiver quality.'
(P/('evidence/quadrature-ac-comparison.json' if ACCOUPLED else 'evidence/quadrature-lo-driver-comparison.json')).write_text(json.dumps(out,indent=2)+'\n');print(out['status'],out['completed']);print(out.get('windows',[])[-1:]);print(out.get('power',[]))
