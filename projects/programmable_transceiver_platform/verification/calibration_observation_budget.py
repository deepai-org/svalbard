"""Observation feasibility audit, not a physical bound or calibration approval."""
import json,math,hashlib
from pathlib import Path
from statistics import NormalDist
P=Path(__file__).resolve().parents[1]

def main():
    paths=[P/'evidence'/f'connected-limited-rail20-pad-quality-mode{m}-three-cap-phase-diagnostic.json' for m in (0,1)]
    rows=[]
    tolerance=.001
    bits=12
    # Quantizer uses round(value * 2**(bits-1)); do not divide systematic
    # quantization uncertainty by sqrt(N) without a dither assumption.
    quantization_half_lsb=1/(2*2**(bits-1))
    for path in paths:
        r=json.loads(path.read_text())
        sigma=r['traffic']['reference_metrics']['frontend']['noise_rms_per_component']
        for confidence in (.95,.99,.999):
            z=NormalDist().inv_cdf((1+confidence)/2)
            estimates=[]
            for count in (1,16,64,256):
                half_width=z*sigma/math.sqrt(count)+quantization_half_lsb
                estimates.append(dict(samples=count,optimistic_half_width_v=half_width,
                    remaining_residual_allowance_v=max(0.,tolerance-half_width)))
            required=math.ceil((z*sigma/(tolerance-quantization_half_lsb))**2)
            rows.append(dict(mode=r['mode'],confidence=confidence,noise_rms_v=sigma,
                minimum_samples_zero_residual_optimistic=required,estimates=estimates))
    # Gaussian single-observation coverage of the prior fixture bound: even
    # before reference, quantization or other errors it is only ~23.6%.
    coverage=2*NormalDist().cdf(.0003/.001)-1
    assert .235<coverage<.237
    report=dict(status='observation_budget_only',tolerance_v=tolerance,
        quantization_half_lsb_v=quantization_half_lsb,
        noise_only_coverage_of_300uv_bound=coverage,rows=rows,
        input_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        limitations=['Gaussian noise has unbounded support; confidence is not a deterministic bound.',
        'Independent samples and known stationary variance assumed; correlation reduces averaging benefit.',
        'Optimistic unity gain/reference scaling; actual reference, gain, supply, settling and drift uncertainties still required.',
        'A near-zero observed mean is required; sample count alone cannot approve calibration.',
        'No controller status or chip acceptance gate changed; 99.9% is exploratory, not an approved failure probability.'])
    (P/'evidence/calibration-observation-budget.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Noise-only coverage of assumed 300 uV bound:',coverage)
    for row in rows:
        print('mode',row['mode'],'confidence',row['confidence'],'optimistic minimum N',row['minimum_samples_zero_residual_optimistic'])
if __name__=='__main__':main()
