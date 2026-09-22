"""Compare integer-edge sequences at the same carriers and unchanged lock limits."""
import hashlib,json
from pathlib import Path
from fractions import Fraction
from chip_model import P
from fractional_rf_chip import ShapedRFClock
from fractional_pulse_pll import DividerSequence
from shaped_fractional_pll import SecondOrderSequence
from pll_filter_tradeoff_screen import measure

class FirstOrderRFClock(ShapedRFClock):
    SEQUENCE_CLASS=DividerSequence

if __name__=='__main__':
    # Exact rational frequency and positive integer intervals before dynamic tests.
    for target in (2412000000,2437000000):
        ratio=Fraction(target,40000000)
        for cls in (DividerSequence,SecondOrderSequence):
            seq=cls(ratio);counts=[seq.step() for _ in range(4*ratio.denominator)]
            assert all(isinstance(v,int) and v>0 for v in counts)
            assert sum(counts)==4*ratio.numerator
    result=dict(status='running',cases=[],source_sha256={str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')},limitations=[
        'Isolated noisy loop with held supply pull; not full-chip startup or payload quality.',
        'Same carrier, integer physical divider edges, pump compliance and sustained-lock thresholds.',
        'Reference-edge phase samples do not qualify continuous RF emissions or all inter-edge ripple.'])
    output=P/'evidence/pll-sequence-tradeoff-screen.json'
    for target in (2412000000,2437000000):
        for bw in (300e3,450e3,600e3):
            for cls in (ShapedRFClock,FirstOrderRFClock):
                row=measure(bw,.3,target,20000.,cls);row['sequence']=cls.SEQUENCE_CLASS.__name__
                result['cases'].append(row);output.write_text(json.dumps(result,indent=2)+'\n');print(row,flush=True)
    result['status']='characterized';output.write_text(json.dumps(result,indent=2)+'\n')
