"""Fixed-window Gaussian residual assessment; never a deterministic guarantee.

Observation model: y_i = gain_i * residual + e_i + noise_i, where each
positive gain is inside a declared interval, abs(e_i) <= systematic_bound_v,
and noise is independent zero-mean Gaussian with known sigma <= noise_sigma_v.
The residual must remain constant over the predetermined observation window.
All voltages except the residual tolerance are in decoded-observation units.
"""
import math
from statistics import NormalDist


def assess_samples(samples, *, planned_samples, confidence, noise_sigma_v,
                   systematic_bound_v, gain_interval, tolerance_v,
                   assumptions_validated=False, quiet=True, clipped=False,
                   epoch=0, observation_epoch=0, range_limited=False):
    if type(planned_samples) is not int or planned_samples<1:
        raise ValueError('Positive predetermined sample count required')
    if not math.isfinite(confidence) or not 0<confidence<1:
        raise ValueError('Confidence must be strictly between zero and one')
    if not math.isfinite(tolerance_v) or tolerance_v<=0:
        raise ValueError('Positive finite residual tolerance required')
    values=tuple(samples)
    if any(not math.isfinite(v) for v in values):
        raise ValueError('Nonfinite observation')
    result=dict(accuracy='unverified',valid=False,statistical_pass=False,
                confidence=confidence,samples=len(values),planned_samples=planned_samples,
                interpretation='Per fixed window; conditional on declared observation assumptions')
    if len(values)!=planned_samples:
        result['reason']='incomplete or mismatched fixed observation window';return result
    if not quiet or epoch!=observation_epoch or clipped:
        result['reason']='not quiet, stale, or clipped observation';return result
    if range_limited:
        result.update(accuracy='failed',reason='trim range exhausted');return result
    if not assumptions_validated or any(v is None for v in (noise_sigma_v,systematic_bound_v,gain_interval)):
        result['reason']='observation assumptions or uncertainty budget unverified';return result
    if any(not math.isfinite(v) or v<0 for v in (noise_sigma_v,systematic_bound_v)):
        raise ValueError('Invalid observation uncertainty')
    if len(gain_interval)!=2:
        raise ValueError('Two gain bounds required')
    gmin,gmax=gain_interval
    if not all(math.isfinite(g) for g in (gmin,gmax)) or not 0<gmin<=gmax:
        raise ValueError('Positive ordered observation gains required')
    # This formulation remains finite for confidence close to 1.
    z=-NormalDist().inv_cdf((1-confidence)/2)
    mean=math.fsum(values)/planned_samples
    half=z*noise_sigma_v/math.sqrt(planned_samples)+systematic_bound_v
    endpoints=[(mean+sign*half)/gain for sign in (-1,1) for gain in (gmin,gmax)]
    low,high=min(endpoints),max(endpoints)
    result.update(mean_observation_v=mean,observation_half_width_v=half,
                  residual_confidence_interval_v=[low,high])
    if low>=-tolerance_v and high<=tolerance_v:
        result.update(accuracy='statistically_qualified',statistical_pass=True,
                      reason='confidence interval meets tolerance; deterministic validity remains unverified')
    elif low>tolerance_v or high<-tolerance_v:
        result.update(accuracy='statistical_failure',reason='confidence interval excludes tolerance region')
    else:
        result['reason']='confidence interval overlaps tolerance boundary'
    return result
