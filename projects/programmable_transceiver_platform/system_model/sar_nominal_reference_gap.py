"""Expose remaining gap when autonomous SAR search assumes nominal rails."""
import hashlib,json,sys
from pathlib import Path
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'system_model/connected'))
from sar_charge import convert,controls
controls()
fit=P/'evidence/sar-top-load-fit.json';beta=json.loads(fit.read_text())['beta']
physical=P/'evidence/sar-driver-physical.json';d=json.loads(physical.read_text());assert d['completed']
rows=[]
for case in d['cases']:
    if case['name']=='sar-physical-control-100':continue
    for f in case['frames']:
        anchor=f['decisions'][0]['preclock_residue_v']
        code,steps=convert(anchor,extra_cap_ratio=1/beta-1)
        disagreements=[s['bit'] for s,v in zip(steps,f['decisions']) if (s['residue_v']<=0)!=(v['preclock_residue_v']<=0)]
        rows.append(dict(case=case['name'],hold_ns=f['hold_ns'],held_anchor_v=anchor,
            nominal_reference_predicted_code=code,physical_code=f['final_code'],
            code_error=code-f['final_code'],first_sign_divergence_bit=disagreements[0] if disagreements else None))
out=dict(beta=beta,results=rows,source_hashes={str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
    (Path(__file__),fit,physical,P/'system_model/connected/sar_charge.py')},
    limitations=['Only held anchor comes from the physical conversion; subsequent nominal-rail search is causal.',
      'After first divergence, physical and modeled switching histories differ.',
      'Nominal reference error is not a claim that all discrepancies have one cause.'])
(P/'evidence/sar-nominal-reference-gap.json').write_text(json.dumps(out,indent=2)+'\n')
for r in rows:print(r['case'],r['hold_ns'],r['nominal_reference_predicted_code'],r['physical_code'])
