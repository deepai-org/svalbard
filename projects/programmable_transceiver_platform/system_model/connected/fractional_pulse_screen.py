"""Divider arithmetic, pulse feedback and measured deterministic timing ripple."""
import cmath,copy,json,math
from fractions import Fraction
from chip_model import P
from fractional_pulse_pll import DividerSequence,FractionalPulsePLL

def run(rate,pll_class=FractionalPulsePLL,bandwidth_hz=1e6):
    ratio=Fraction(rate,40000000);d=pll_class.SEQUENCE_CLASS(ratio)
    counts=[d.step() for _ in range(2*ratio.denominator)]
    assert sum(counts)==2*ratio.numerator and d.accumulator==0
    assert all(0<n and d.low-1<=n<=d.low+2 for n in counts)
    p=pll_class(rate_hz=rate,bandwidth_hz=bandwidth_hz);assert p.advance(40e-6)
    before=(p.phase,p.time,p.sequence.accumulator,p.sequence.emitted,p.sequence.total)
    target=p.phase+123.5;crossing=p.edge_time(target)
    assert before==(p.phase,p.time,p.sequence.accumulator,p.sequence.emitted,p.sequence.total)
    trial=copy.copy(p);assert trial.advance(crossing) and abs(trial.phase-target)<2e-8
    dense=copy.copy(p)
    start=p.time;initial=p.phase;points=[]
    for i in range(1,801):
        t=start+i/40e6;assert p.advance(t);points.append((t-start,p.phase-initial))
    slope=points[-1][1]/points[-1][0]
    residual=[phase-slope*t for t,phase in points]
    mean=sum(residual)/len(residual)
    rms=math.sqrt(sum((x-mean)**2 for x in residual)/len(residual))/rate
    ppm=(slope/rate-1)*1e6
    assert abs(ppm)<1000,ppm # Numerical tracking sanity, not a protocol tolerance.
    dense_points=[]
    for i in range(1,12801):
        t=start+i/(16*40e6);assert dense.advance(t)
        dense_points.append((t-start,dense.phase-initial))
    dense_slope=dense_points[-1][1]/dense_points[-1][0]
    dense_residual=[phase-dense_slope*t for t,phase in dense_points]
    center=sum(dense_residual)/len(dense_residual)
    dense_rms=math.sqrt(sum((x-center)**2 for x in dense_residual)/len(dense_residual))/rate
    assert abs(dense.phase-p.phase)<1e-6
    phasors=[cmath.exp(2j*math.pi*x) for x in dense_residual]
    carrier=sum(phasors)/len(phasors)
    phase_only_error=math.sqrt(sum(abs(z-carrier)**2 for z in phasors)/len(phasors))/abs(carrier)
    return dict(loop_class=pll_class.__name__,bandwidth_hz=bandwidth_hz,
        phase_only_relative_rms=phase_only_error,dense_timing_rms_s=dense_rms,
        dense_timing_peak_to_peak_s=(max(dense_residual)-min(dense_residual))/rate,
        dense_observation_step_s=1/(16*40e6),target_hz=rate,divider_observation_cycles=len(counts),integer_counts=counts,mean_frequency_error_ppm=ppm,
        detrended_timing_rms_s=rms,detrended_timing_peak_to_peak_s=(max(residual)-min(residual))/rate,
        final_locked=p.locked,compliance_margin_v=p.metrics()['minimum_compliance_margin_v'])

def main():
    rows=[run(r) for r in (2412000000,2437000000)]
    (P/'evidence/connected-fractional-pulse.json').write_text(json.dumps(dict(status='passed',cases=rows,
        complete_architecture=False,physical_qualification=False,
        limitations=['Passing validates integer-divider arithmetic and simulation, not RF quality or lock qualification.',
        'First-order periodic modulation can create deterministic spurs; no noise shaping or dither.',
        'Loop filter uses the lower integer-band design; tuning-gain variation and divider hardware are unqualified.']),indent=2)+'\n')
    print('Fractional pulse measurements:',rows,flush=True)
if __name__=='__main__':main()
