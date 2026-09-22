"""Exact RC-rail phase forcing and actual serializer deadline retiming."""
import copy,json,math
from chip_model import P
from compliant_edge_pll import CompliantEdgePLL
from pll_serializer import PLLSerializer
from wired_blocks import WiredChannel

def run(rate,sign):
    p=CompliantEdgePLL(rate_hz=rate,reference_hz=10e6);assert p.advance(20e-6) and p.locked
    p.set_reference(False,p.time);base=copy.copy(p)
    before=(p.phase,p.filter.v,p.filter.w);start=p.time
    p.set_supply(start,sign*.1,100e-9,1e6)
    assert before==(p.phase,p.filter.v,p.filter.w)
    split=copy.copy(p);end=start+1e-6
    p.advance(end);base.advance(end)
    for i in range(1,138):split.advance(start+1e-6*i/137)
    expected=sign*.1*1e6*100e-9*(-math.expm1(-10))
    error=abs(p.phase-base.phase-expected)
    assert error<1e-8 and abs(split.phase-p.phase)<1e-7
    old=(p.time,p.phase,p.rail_amplitude_hz)
    try:p.set_supply(p.time+1e-6,-1,1e-6,1e12)
    except ValueError:pass
    else:raise AssertionError('Reversing VCO accepted')
    assert old==(p.time,p.phase,p.rail_amplitude_hz)
    q=CompliantEdgePLL(rate_hz=rate,reference_hz=10e6);q.advance(20e-6)
    s=PLLSerializer(WiredChannel(rate),q.time,q);words=[17,801,0,1023,511,7];out=[]
    origin=q.phase;change=None
    for i,word in enumerate(words):
        s.start(word,q.edge_time(origin+10*i),1/rate)
        injected=False
        while s.active:
            if i==3 and s.bit==4 and s.stage=='sample' and not injected:
                before=q.phase;old_deadline=s.deadline
                q.set_supply(q.time,sign*.1,100e-9,1e6);assert q.phase==before
                s.retime();change=s.deadline-old_deadline
                assert change*sign<0;injected=True
            result=s.step()
            if result is not None:out.append(result)
    assert out==words and s.channel.errors==0
    return dict(rate_hz=rate,sign=sign,analytic_phase_error_cycles=error,deadline_change_s=change,words=len(out))

def main():
    rows=[run(r,s) for r in (1.25e9,2.5e9) for s in (-1,1)]
    (P/'evidence/connected-pump-supply.json').write_text(json.dumps(dict(status='passed',cases=rows,
        complete_architecture=False,physical_qualification=False,
        limitations=['Assumed linear frequency sensitivity and one exponentially recovering rail.',
        'Pump current, filter leakage and reference timing are not supply-sensitive in this model.',
        'Full-chip pulse-loop substitution and stochastic noise remain open.']),indent=2)+'\n')
    print('Passed pulse-loop RC forcing, continuity, invalid-range rejection and serializer retiming')
if __name__=='__main__':main()
