"""Bit-level TX equivalence, completion timing and analog tail after partial abort."""
import json,math
from chip_model import P
from wired_blocks import WiredChannel
from wired_serializer import Serializer
from timed_lifecycle import TimedChip


def controls():
    for rate in (1.25e9,2.5e9):
        for tap in (0.,.25,.5):
            reference=WiredChannel(rate,swing=.5,postcursor=tap)
            actual=WiredChannel(rate,swing=.5,postcursor=tap);s=Serializer(actual,0)
            for i,word in enumerate((17,801,3,999,0,1023)):
                start=i*10/rate;s.start(word,start,1/rate);out=[]
                while s.active:
                    value=s.step()
                    if value is not None:out.append(value)
                assert out==[reference.word(word)] and abs(s.time-(start+9.5/rate))<1e-22
                s.advance((i+1)*10/rate);assert abs(actual.state-reference.state)<1e-13
            assert s.accounting()['completed']==6


def run(mode,position):
    c=TimedChip();c.configure(mode,0);c.advance(c.acquisition_s)
    c.accept_wire(0x155);start=c.time+100e-9;c.schedule_wire(1,start)
    ui=c.wire_period/10;cut=start+position*ui;c.advance(cut)
    assert not c.wired_output and c.serializer.active
    retained=c.channel.state;sampled=c.channel.bits
    c.set_reference(False,cut)
    assert c.channel.state==retained and c.serializer.accounting()['aborted']==1
    c.advance(cut+10*ui)
    assert abs(c.channel.state-retained*math.exp(-c.serializer.pole*10*ui))<1e-13
    assert not c.wired_output and c.channel.bits==sampled
    return dict(mode=mode,cut_ui=position,sampled_bits=sampled,serializer=c.serializer.accounting())


def main():
    controls();rows=[run(m,p) for m in (0,1) for p in (.25,3.25,9.25)]
    report=dict(status='passed',cases=rows,complete_architecture=False,physical_qualification=False,
        limitations=['Bit clock remains a prescribed local period; autonomous wired TX PLL and supply/jitter response remain open.',
        'Peer samples at prescribed mid-bit instants; this TX observation is not a second recovered receiver.',
        'Cross-mode external channel persistence is tested separately; termination switching and package response remain unmodeled.'])
    (P/'evidence/connected-wired-bit-timing.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed six rate/shaping equivalence controls and six partial-word abort cases')

if __name__=='__main__':main()
