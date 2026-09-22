#!/usr/bin/env python3
"""Predeclare sampler-only timing perturbations and audit ideal source relationships."""
import hashlib,json,re
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-adc-shared-iq-damping2k'
d=(W/'frames.spice').read_text();h=hashlib.sha256(d.encode()).hexdigest();assert h==json.loads((W/'manifest.json').read_text())['deck_sha256_before']
def pairs(source):
 line=next(x for x in d.splitlines() if x.startswith(source+' '));m=re.search(r'PWL\(([^)]+)\)',line);tokens=m[1].split();assert len(tokens)%2==0
 return [(float(tokens[i].removesuffix('n')),float(tokens[i+1])) for i in range(0,len(tokens),2)]
def ramps(source,rising):
 p=pairs(source);return [(a[0],b[0]) for a,b in zip(p,p[1:]) if (b[1]>a[1] if rising else b[1]<a[1])]
sc=ramps('VS',False);scb=ramps('VSB',True);mask=ramps('VMASK',True);clk=ramps('VC',True)
assert sc==scb and len(sc)==3 and len(mask)==3
rows=[]
for delta in (-.1,0.,.1):
 for i,(start,end) in enumerate(sc):
  first=next(a for a,b in clk if a>=start)
  assert abs(mask[i][0]-start)<1e-12
  rows.append(dict(offset_ns=delta,frame=i,sampler_ramp_ns=[start+delta,end+delta],mask_ramp_ns=list(mask[i]),first_comparator_rise_ns=first,ideal_end_to_comparator_gap_ns=first-end-delta))
assert min(x['ideal_end_to_comparator_gap_ns'] for x in rows)>.29
out=dict(status='verified_source_schedule_for_proposed_sampler_only_test',deck_sha256=h,cases=rows,limitations=['Proposed experiment only; no perturbed simulation run.','Shift both complementary sampler controls together; leave mask/conversion/reset/input schedules unchanged.','Positive shift overlaps mask release intentionally and tests that interaction; not a pure observation-time shift.','Ideal source gaps exclude physical control/comparator delays and are not setup-time qualification.','Both offsets are diagnostic scenarios, not guaranteed jitter bounds.'])
(P/'evidence/adc-edge-perturbation-plan.json').write_text(json.dumps(out,indent=2)+'\n');print('9 cases; minimum ideal gap',min(x['ideal_end_to_comparator_gap_ns'] for x in rows),'ns')
