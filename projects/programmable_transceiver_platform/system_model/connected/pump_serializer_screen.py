"""Actual charge-pump loop phase drives existing wired serializer/channel."""
import copy,json,math
from chip_model import P
from compliant_edge_pll import CompliantEdgePLL
from pll_serializer import PLLSerializer
from wired_blocks import WiredChannel

def snapshot(p):
    return (p.time,p.phase,p.filter.__dict__.copy(),list(p.reference_history),list(p.transitions),p.feedback_target)

def run(rate):
    p=CompliantEdgePLL(rate_hz=rate,reference_hz=10e6)
    assert p.advance(20e-6) and p.locked
    before=snapshot(p)
    target=p.phase+25.5;t=p.edge_time(target)
    assert snapshot(p)==before
    forecast=copy.copy(p);assert forecast.advance(t)
    assert abs(forecast.phase-target)<2e-8 and snapshot(p)==before
    channel=WiredChannel(rate);s=PLLSerializer(channel,p.time,p)
    words=[17,801,0,1023,511,7]*3;out=[];phase=p.phase;residual=0.
    for i,word in enumerate(words):
        start=p.edge_time(phase+10*i)
        s.start(word,start,1/rate)
        while s.active:
            expected=s.target_phase;result=s.step()
            residual=max(residual,abs(p.phase-expected))
            if result is not None:out.append(result)
    assert out==words and channel.errors==0 and residual<2e-8
    return dict(rate_hz=rate,words=len(words),maximum_phase_residual_cycles=residual,
        first_lock_s=p.first_lock,clock=p.metrics(),serializer=s.accounting())

def main():
    rows=[run(r) for r in (1.25e9,2.5e9)]
    (P/'evidence/connected-pump-serializer.json').write_text(json.dumps(dict(status='passed',cases=rows,
        complete_architecture=False,physical_qualification=False,
        limitations=['Nominal integer-N loops and assumed compliance current law, not GF180 clock qualification.',
        'RF envelope, fractional tuning, reference-loss holdover and supply/noise forcing are not yet adapted.',
        'Full-chip entry still uses sampled PLLs; this validates one real consumer of the pulse-loop phase service.']),indent=2)+'\n')
    print('Passed pump-clock serializer transport and side-effect-free phase forecasting')
if __name__=='__main__':main()
