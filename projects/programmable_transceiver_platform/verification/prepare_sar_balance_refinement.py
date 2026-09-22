"""Matched maximum-timestep refinement; no tolerance relaxation."""
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for label,parent in [('baseline','sar-bottom-plates'),('instrumented','sar-reference-balance')]:
    B=R/f'scratch/transceiver-{parent}-prepared';O=R/f'scratch/transceiver-sar-balance-refined-{label}-prepared'
    m=json.loads((B/'manifest.json').read_text());assert sha(B/'baseline.spice')==m['artifacts_sha256']['baseline.spice']
    s=(B/'baseline.spice').read_text();old='tran 5p 209.9n 0 5p';new='tran 5p 209.9n 0 2.5p'
    assert s.count(old)==1;candidate=s.replace(old,new);assert candidate.replace(new,old)==s
    O.mkdir();(O/'baseline.spice').write_text(candidate)
    m.update(candidate='Matched maximum-timestep refinement: '+label,
        parent=parent,parent_preparation_sha256=sha(B/'manifest.json'),
        artifacts_sha256={'baseline.spice':sha(O/'baseline.spice')},
        qualification_plan=['Require full clean run and unchanged source provenance.',
          'Compare refined original/instrumented waveforms with unchanged10uV limit and24 matching decisions.',
          'Also report each refined run versus its5ps parent; do not claim convergence solely from cross-deck agreement.'],
        reproduction=dict(window_ns=[70,209],analog_maximum_error_v=1e-5,all_decisions_match=True),
        limitations=['One timestep refinement diagnoses sensitivity but does not prove asymptotic convergence.'])
    (O/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print(O)
