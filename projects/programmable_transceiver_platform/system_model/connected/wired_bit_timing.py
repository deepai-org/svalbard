"""Prescribed bit-phase serializer equivalence; no receiver CDR or chip lifecycle."""
from wired_blocks import WiredChannel
from wired_serializer import Serializer

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


if __name__=="__main__":
    controls()
    print("Serializer/channel equivalence controls passed.")
