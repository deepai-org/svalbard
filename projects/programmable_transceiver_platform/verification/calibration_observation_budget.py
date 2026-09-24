"""Observation feasibility audit, not a physical bound or calibration approval."""
import json,math,hashlib
from pathlib import Path
from statistics import NormalDist
P=Path(__file__).resolve().parents[1]

def residual_interval(code, *, bits=12, span, gain, additive, recovery):
    """Invert an interior rounded code through declared bounded linear errors.

    Model: quantizer input = (gain * residual + additive) / span + recovery.
    Bounds are caller evidence, not inferred from a zero code. Compression,
    clipping and unbounded noise cannot be qualified by this calculation.
    """
    from itertools import product
    if type(bits) is not int or not 2<=bits<=24:
        raise ValueError('Supported integer converter precision required')
    scale=1 << (bits-1)
    if type(code) is not int or not -scale<code<scale-1:
        raise ValueError('Interior signed code required; rail codes are ambiguous')
    intervals=[]
    for name,bound in (('span',span),('gain',gain),('additive',additive),('recovery',recovery)):
        if bound is None or len(bound)!=2 or not all(math.isfinite(v) for v in bound):
            raise ValueError('Finite two-sided '+name+' bound required')
        lo,hi=bound
        if lo>hi or (name in ('span','gain') and lo<=0):
            raise ValueError('Ordered bounds and positive gain/reference required')
        intervals.append((lo,hi))
    q=code/scale;half_lsb=.5/scale
    values=[(s*(q+e-r)-n)/g for s,g,n,r,e in
            product(*intervals,(-half_lsb,half_lsb))]
    return min(values),max(values)


def bounded_controls():
    """Independent forward trials and invalid-envelope controls, not chip proof."""
    import random
    bounds=dict(span=(.98,1.02),gain=(.98,1.02),additive=(-50e-6,50e-6),
                recovery=(-50e-6,50e-6))
    interval=residual_interval(0,**bounds)
    expected=(1.02*(.5/2048+50e-6)+50e-6)/.98
    assert abs(interval[0]+expected)<1e-18 and abs(interval[1]-expected)<1e-18
    rng=random.Random(92831)
    for _ in range(4000):
        s,g,n,r=(rng.uniform(*bounds[key]) for key in ('span','gain','additive','recovery'))
        truth=rng.uniform(-.8,.8)
        code=round(((g*truth+n)/s+r)*2048)
        lo,hi=residual_interval(code,**bounds)
        assert lo<=truth<=hi
    rejected=0
    for code,change in ((-2048,{}),(2047,{}),(0,dict(span=(0.,1.))),
                        (0,dict(gain=(-1.,1.))),(0,dict(additive=None)),
                        (0,dict(recovery=(-math.inf,math.inf))),
                        (0,dict(span=(1.02,.98)))):
        try:residual_interval(code,**(bounds|change))
        except ValueError:rejected+=1
        else:raise AssertionError('Invalid observation envelope accepted')
    return dict(status='conditional_interval_controls_passed',forward_trials=4000,
        invalid_envelopes_rejected=rejected,zero_code_interval_v=interval,
        assumed_bounds=bounds,physical_qualification=False,chip_calibration_validity_changed=False)


def canonical_controls(nonideal=False):
    """Known-input checks on canonical ADC composition; no routing qualification."""
    from full_chip_model import make_chip
    from receiver_impairments import Frontend
    from adc_recovery import ADCRecovery
    rows=[]
    settings=[(0.,0.)] if not nonideal else [(g,p) for g in (-.02,.02) for p in (-.03,.03)]
    for gain_error,phase_error in settings:
        chip=make_chip();chip.bits=12
        if nonideal:
            chip.frontend=Frontend(gain_error=gain_error,phase_error=phase_error)
            chip.adc_recovery=ADCRecovery(tau_s=200e-9,gain=.05)
            chip.adc_recovery.residual=complex(150e-6,-150e-6)
        assert chip.coupling==0 and chip.frontend.noise==0 and chip.frontend.sat is None
        for index,value in enumerate((0.,.0001,-.0001,.0008,-.0008,.0012,-.0012,.01)):
            chip.advance((index+1)*25e-9)
            if index%2==0:chip.emitted_return_word(1023 if index%4==0 else 0,chip.time)
            before=chip.adc_reference.voltage;samples=chip.adc_reference.samples
            word=chip.convert_adc(complex(value,-value))
            assert chip.adc_reference.samples==samples+1 and chip.adc_reference.voltage<before
            for shift,truth in ((0,value),(12,-value)):
                code=(word>>shift)&4095
                if code>=2048:code-=4096
                # Bounds cover both signs of gain/phase and the entire known
                # input range, not the particular residual being reconstructed.
                bounds=dict(span=(before-.001,before+.001),
                    gain=(.98*math.cos(.03),1.02),
                    additive=(-1.02*.01*math.sin(.03),1.02*.01*math.sin(.03)),
                    recovery=(-150e-6,150e-6)) if nonideal else dict(
                        span=(before,before),gain=(1.,1.),additive=(0.,0.),recovery=(0.,0.))
                low,high=residual_interval(code,**bounds)
                assert low<=truth<=high
                rows.append(dict(time_s=chip.time,axis='I' if shift==0 else 'Q',
                    gain_error=gain_error,phase_error_rad=phase_error,input_v=truth,code=code,
                    reference_before_v=before,reference_after_v=chip.adc_reference.voltage,
                    residual_interval_v=[low,high],bounded_within_1mv=low>=-.001 and high<=.001))
    return dict(status='canonical_transfer_control_passed',nonideal=nonideal,cases=rows,
        physical_qualification=False,chip_calibration_validity_changed=False,
        limitations=['Known injected ADC inputs, not an independent calibration observation route.',
            'Nonideal settings and error envelopes are hypotheses; no Gaussian noise or compression.',
            'Verifier observes pre-sample reference; the nonideal interval adds assumed 1 mV uncertainty.',
            'Recovery starts with assumed bounded memory; no new overloads occur in this input range.'])


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
    report=dict(status='observation_budget_only',bounded_controls=bounded_controls(),tolerance_v=tolerance,
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
if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    modes=parser.add_mutually_exclusive_group()
    modes.add_argument('--bounded-controls',action='store_true')
    modes.add_argument('--canonical-controls',action='store_true')
    modes.add_argument('--nonideal-controls',action='store_true')
    args=parser.parse_args()
    if args.nonideal_controls:print(json.dumps(canonical_controls(nonideal=True),indent=2))
    elif args.canonical_controls:print(json.dumps(canonical_controls(),indent=2))
    elif args.bounded_controls:print(json.dumps(bounded_controls(),indent=2))
    else:main()
