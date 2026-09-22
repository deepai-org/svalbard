#!/usr/bin/env python3
"""Inspect exported samples near source edge; preserve decimal print precision."""
import hashlib,json
from decimal import Decimal,localcontext
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-mixed-passive'
r=json.loads((W/'result.json').read_text());rows=[]
with localcontext() as ctx:
 ctx.prec=50
 endpoint=Decimal('0.0000006377');slope=Decimal('33000000000')
 for c in r['cases']:
  name=c['name'];file=W/(name+'.dat');assert hashlib.sha256(file.read_bytes()).hexdigest()==c['artifacts_sha256']['.dat'];samples=[]
  with file.open() as f:
   assert f.readline().lower().split()==['time','v(ref)','v(fb)','v(ro)','v(fo)']
   for line in f:
    fields=line.split();t=Decimal(fields[0])
    if t<endpoint-Decimal('1e-15'):continue
    if t>endpoint+Decimal('1e-15'):break
    ref,fb=Decimal(fields[1]),Decimal(fields[2])
    # Only infer remaining ramp time where the reported source is positive.
    samples.append(dict(time_s=str(t),reference_v=str(ref),feedback_v=str(fb),inferred_reference_falling_endpoint_s=str(t+ref/slope) if ref>0 else None,inferred_feedback_falling_endpoint_s=str(t+fb/slope) if fb>0 else None))
  deltas=[Decimal(b['time_s'])-Decimal(a['time_s']) for a,b in zip(samples,samples[1:])];assert all(x>=0 for x in deltas)
  rows.append(dict(name=name,edge_ns=637.7,samples=samples,zero_printed_steps=sum(x==0 for x in deltas),minimum_positive_printed_step_s=str(min(x for x in deltas if x>0)) if any(x>0 for x in deltas) else None))
out=dict(status='decimal_export_breakpoint_audit',cases=rows,limitations=['Decimal arithmetic avoids further analysis rounding, but cannot recover precision discarded by simulator export.', 'Endpoint extrapolation assumes the specified linear100ps falling ramp and ignores clamped-zero samples.', 'This does not expose the simulator internal event queue or prove why active circuits abort.'])
(P/'evidence/clock-breakpoint-spacing.json').write_text(json.dumps(out,indent=2)+'\n')
for x in rows:print(x['name'],len(x['samples']),'near-edge samples;',x['zero_printed_steps'],'equal printed intervals; min positive',x['minimum_positive_printed_step_s'])
