"""Observation feasibility audit, not a physical bound or calibration approval."""
import json,math,hashlib,sys
from pathlib import Path
from statistics import NormalDist
P=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(P/'system_model/architecture_fast'))
from design_definition import load_design

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
    """Explicit 12-bit round-quantizer primitive control, not native chip precision or chip proof."""
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
    return dict(status='conditional_interval_controls_passed',fixture_bits=12,
        scope='Round-quantizer interval arithmetic at explicit primitive precision; not native chip behavior',forward_trials=4000,
        invalid_envelopes_rejected=rejected,zero_code_interval_v=interval,
        assumed_bounds=bounds,physical_qualification=False,chip_calibration_validity_changed=False)


def observation_budget(design=None, *, tolerance_v=.001):
    from converter_dynamics import parameters_from_inventory
    design=load_design() if design is None else design
    architecture=design.architecture
    parameters=parameters_from_inventory(architecture)
    bits=architecture['blocks']['adc_i']['parameters']['native_bits']
    if isinstance(tolerance_v,bool) or not isinstance(tolerance_v,(int,float)) or not math.isfinite(tolerance_v) or tolerance_v<=0:
        raise ValueError('Positive finite diagnostic residual tolerance required')
    tolerance=float(tolerance_v)
    # Optimistic centered quantizer: systematic uncertainty does not average
    # down without an independently justified dither/calibration model.
    quantization_half_lsb=1/(2*2**(bits-1))
    sigma=parameters.comparator_noise_rms_v
    rows=[]
    for confidence in (.95,.99,.999):
        z=NormalDist().inv_cdf((1+confidence)/2)
        estimates=[]
        for count in (1,16,64,256):
            half_width=z*sigma/math.sqrt(count)+quantization_half_lsb
            estimates.append(dict(samples=count,optimistic_half_width_v=half_width,
                remaining_residual_allowance_v=max(0.,tolerance-half_width)))
        required=(max(1,math.ceil((z*sigma/(tolerance-quantization_half_lsb))**2))
                  if tolerance>quantization_half_lsb else None)
        rows.append(dict(confidence=confidence,noise_rms_v=sigma,
            minimum_samples_zero_residual_optimistic=required,estimates=estimates))
    # Gaussian single-observation coverage of the prior fixture bound: even
    # before reference, quantization or other errors it is only ~23.6%.
    coverage=2*NormalDist().cdf(.0003/sigma)-1 if sigma else 1.
    assert 0<=coverage<=1
    report=dict(design_provenance=design.provenance(),status='observation_budget_only',native_bits=bits,
        model_role='shared_converter_parameters_with_diagnostic_observation_assumptions',
        diagnostic_assumptions=dict(residual_tolerance_v=tolerance,quantizer_positive_span_v=1.,
            confidence_levels=[.95,.99,.999],sample_counts=[1,16,64,256],
            historical_single_observation_bound_v=.0003,
            scope='Requirement exploration, not selectable hardware settings or an approved calibration gate'),
        noise_assumption='Selected comparator RMS used as an illustrative independent input-referred Gaussian error; not a measured ADC output-noise model',bounded_controls=bounded_controls(),tolerance_v=tolerance,
        quantization_half_lsb_v=quantization_half_lsb,
        noise_only_coverage_of_300uv_bound=coverage,rows=rows,
        sources_sha256={str(path.relative_to(P)):hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (Path(__file__),P/'verification/converter_dynamics.py',P/'system_model/architecture_fast/design_definition.py')},
        limitations=['Gaussian noise has unbounded support; confidence is not a deterministic bound.',
        'Independent samples and known stationary variance assumed; correlation reduces averaging benefit.',
        'Optimistic centered round quantizer, not a characterization of SAR transition thresholds or DNL/INL.',
        'Optimistic unity gain/reference scaling; actual reference, gain, supply, settling and drift uncertainties still required.',
        'A near-zero observed mean is required; sample count alone cannot approve calibration.',
        'No controller status or chip acceptance gate changed; 99.9% is exploratory, not an approved failure probability.'])
    return report


def main():
    report=observation_budget()
    coverage=report['noise_only_coverage_of_300uv_bound'];bits=report['native_bits'];rows=report['rows']
    (P/'evidence/calibration-observation-budget.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Noise-only coverage of assumed 300 uV bound:',coverage)
    for row in rows:
        print('native bits',bits,'confidence',row['confidence'],'optimistic minimum N',row['minimum_samples_zero_residual_optimistic'])
if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bounded-controls',action='store_true')
    args=parser.parse_args()
    if args.bounded_controls:print(json.dumps(bounded_controls(),indent=2))
    else:main()
