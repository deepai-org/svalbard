"""Autonomous oscillator drives the existing bit/channel serializer."""
import json
from pathlib import Path
from autonomous_pll import AutonomousPLL
from autonomous_pll_screen import settle
from pll_serializer import PLLSerializer
from wired_blocks import WiredChannel


def run(rate,sign):
    p=AutonomousPLL(divider=rate/40e6,free_hz=rate*(1+sign*.04))
    settle(p,5e-6);assert p.locked
    s=PLLSerializer(WiredChannel(rate),p.time,p)
    words=[17,801,0,1023,511,7]*3;out=[];periods=[]
    start=p.time;phase=p.output_phase_cycles
    for index,word in enumerate(words):
        deadline=p.edge_time(phase+10*index)
        if index:periods.append(deadline-start)
        start=deadline;s.start(word,deadline,1/rate)
        disturbed=False
        while s.active:
            if index==3 and s.bit==4 and s.stage=='sample' and not disturbed:
                intervention=(p.time+s.deadline)/2
                old=s.deadline
                p.disturb(intervention,frequency_hz=sign*10e6)
                s.retime();assert (s.deadline-old)*sign<0
                disturbed=True
            value=s.step()
            if value is not None:out.append(value)
    assert out==words and s.channel.errors==0
    assert max(periods)-min(periods)>1e-12
    assert s.accounting()==dict(started=len(words),completed=len(words),aborted=0,pending=0)
    return dict(rate_hz=rate,disturbance_sign=sign,words=len(words),
                minimum_word_period_s=min(periods),maximum_word_period_s=max(periods))


if __name__=='__main__':
    report=dict(status='passed',complete_architecture=False,physical_qualification=False,cases=[run(r,s) for r in (1.25e9,2.5e9) for s in (-1,1)],
                limitations=['Connected host scheduling, lock gating and shared supply callback are not yet attached.',
                             'Ideal average divider and assumed VCO parameters; no phase-noise qualification.'])
    (Path(__file__).resolve().parents[2]/'evidence/connected-pll-serializer.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
