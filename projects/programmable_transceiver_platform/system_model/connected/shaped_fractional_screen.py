"""Compare real integer divider sequences through the same pulse loop."""
from fractions import Fraction
import json
from chip_model import P
from fractional_pulse_pll import FractionalPulsePLL
from fractional_pulse_screen import run
from shaped_fractional_pll import SecondOrderSequence,ShapedFractionalPLL

def arithmetic(rate):
    d=SecondOrderSequence(Fraction(rate,40000000));counts=[]
    for i in range(1,10001):
        n=d.step();counts.append(n)
        assert d.low-1<=n<=d.low+2 and n>0
        assert abs(Fraction(d.total)-i*d.ratio)<2
    assert Fraction(d.total)==10000*d.ratio
    return dict(rate_hz=rate,minimum_count=min(counts),maximum_count=max(counts),samples=len(counts))

def main():
    rows=[];checks=[arithmetic(r) for r in (2412000000,2437000000)]
    for rate in (2412000000,2437000000):
        for cls,bw in ((FractionalPulsePLL,1e6),(ShapedFractionalPLL,1e6),(ShapedFractionalPLL,500e3)):
            row=run(rate,cls,bw);rows.append(row)
            print(rate,cls.__name__,bw,'timing ps',row['dense_timing_rms_s']*1e12,
                'phase error',row['phase_only_relative_rms'],'locked',row['final_locked'],flush=True)
    (P/'evidence/connected-shaped-fractional.json').write_text(json.dumps(dict(status='passed',cases=rows,arithmetic=checks,
        complete_architecture=False,physical_qualification=False,
        limitations=['Finite deterministic sequences; no dither, calibrated device noise or complete channel sweep.',
        'Phase-only phasor error removes mean phase and measured frequency drift; neither modem EVM nor complete RF conversion.',
        'Passing validates simulation/arithmetic, not current lock qualification or acceptable fractional spurs.']),indent=2)+'\n')
if __name__=='__main__':main()
