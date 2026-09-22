"""Independent nodal closed-loop pole check for phase-branch screening."""
import hashlib,json
import numpy as np
from chip_model import P


def poles(row):
    r,cf,cs,r3,c3=(row[k] for k in ('r_ohm','cf_f','cs_f','r3_ohm','c3_f'))
    # State: pump V, slow V, VCO V, feedback phase error in cycles.
    # Negative feedback current is -Icp*error; error'=Kvco*VCO/N.
    a=1/r;b=1/r3
    matrix=np.array([[-(a+b)/cf,a/cf,b/cf,-100e-6/cf],
        [a/cs,-a/cs,0,0],[b/c3,0,-b/c3,0],[0,0,200e6/(2437/40),0]])
    return np.linalg.eigvals(matrix)


def main():
    original=P/'evidence/pll-filter-resynthesis.json'
    corrected=P/'evidence/pll-filter-resynthesis-corrected.json'
    old=json.loads(original.read_text());new=json.loads(corrected.read_text())
    cases=[]
    for row in new['noise_ripple_frontier']:
        roots=poles(row)
        assert np.max(roots.real)<0, (row,roots)
        cases.append(dict(**row,poles_per_s=[[float(z.real),float(z.imag)] for z in roots]))
    false_margin=[r for r in old['noise_ripple_frontier'] if r['sampled_phase_margin_deg']>180]
    assert false_margin
    unstable=sum(bool(np.max(poles(r).real)>0) for r in false_margin)
    assert unstable==len(false_margin)
    report=dict(status='passed_linear_stability_crosscheck',corrected_frontier_stable=len(cases),
        historical_wrapped_margin_unstable=unstable,cases=cases,
        inputs_sha256={str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (original,corrected)},
        limitations=['Averaged linear negative-feedback model only; no sampled divider, finite pump, or RF quality proof.',
        'Stable poles do not establish acceptable ripple or acquisition; leading candidate already failed edge-driven testing.'])
    (P/'evidence/pll-filter-stability-audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Corrected frontier stable:',len(cases),'Historical false-margin unstable:',unstable)
if __name__=='__main__':main()
