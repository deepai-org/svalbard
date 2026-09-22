"""Diagnostic controls, never acceptance substitutes for noisy fractional operation."""
import hashlib,json
from pathlib import Path
from chip_model import P
from pll_filter_tradeoff_screen import measure

if __name__=='__main__':
    report=dict(status='running',cases=[],limitations=[
        'Zero-noise cases isolate periodic divider/pump behavior, not usable chip performance.',
        '2440MHz integer-ratio control changes carrier by 3MHz; comparison is not an exact same-frequency ablation.',
        'Held supply pull and different startup history; no loaded full-chip claim.',
        'Reference-edge sampled phase may omit inter-edge ripple; no physical jitter claim.'],
        source_sha256={str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')})
    output=P/'evidence/pll-impairment-attribution-screen.json'
    for bw in (300e3,450e3):
        for target in (2437000000,2440000000):
            for noise in (0.,20000.):
                row=measure(bw,.3,target,noise);report['cases'].append(row)
                output.write_text(json.dumps(report,indent=2)+'\n');print(row,flush=True)
    report['status']='characterized';output.write_text(json.dumps(report,indent=2)+'\n')
