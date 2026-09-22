"""Exact finite exponential expansion of weak memoryless cubic RF envelope."""
import math
from tx_power_detector import modulator_terms

def output_terms(terms,*,gain_imbalance_db=0.,phase_error_deg=0.,lo_feedthrough=0j,cubic=0.):
    if not math.isfinite(cubic) or cubic<0:raise ValueError('Invalid compression coefficient')
    linear=modulator_terms(terms,gain_imbalance_db,phase_error_deg,lo_feedthrough)
    # Merge exactly equal rates; no rounding or truncation of physical modes.
    combined={}
    for a,p in linear:combined[p]=combined.get(p,0j)+a
    linear=[(a,p) for p,a in combined.items() if a!=0]
    result=dict(combined)
    if cubic:
        for a,p in linear:
            for b,q in linear:
                for c,r in linear:
                    rate=p+q+r.conjugate()
                    result[rate]=result.get(rate,0j)-cubic*a*b*c.conjugate()
    return [(a,p) for p,a in result.items() if a!=0]
