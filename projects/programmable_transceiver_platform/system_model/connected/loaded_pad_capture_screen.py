"""Host-event capture must observe loaded state, not reapply LO or alter delivery."""
import json,pickle
from chip_model import P
from rf_loaded_detector import LoadedDetector
from loaded_pad_capture import captured
from loaded_pad_observer import observe

class EventFixture:
    def __init__(self):
        self.loaded_tx=LoadedDetector();self.time=0.;self.delivered=[]
    def feed(self,word,epoch,time):
        self.loaded_tx.advance(time,[(.2+.1j,2j*3.141592653589793*7e6)])
        self.time=time;self.delivered.append((word,epoch,time))
        return dict(accepted=True,word=word)

def main():
    instances=[];c=captured(EventFixture,2437000000,instances)();reference=EventFixture()
    for i in range(8):
        time=(i+1)*10e-9
        assert c.feed(i,0,time)==reference.feed(i,0,time)
        assert c.pad_observations[-1]==(time,observe(reference.loaded_tx.network,time,2437000000))
        assert pickle.dumps(c.loaded_tx)==pickle.dumps(reference.loaded_tx)
    c.tx_observe_enabled=False;c.feed(8,0,90e-9)
    assert len(c.pad_observations)==8 and len(c.delivered)==9 and instances==[c]
    report=dict(status='passed',samples=8,limitations=[
        'Host-event fixture verifies capture semantics; real managed framing and waveform qualification remain pending.',
        'Source phase trajectory is synthetic and already included in network voltage.'])
    (P/'evidence/connected-loaded-pad-capture.json').write_text(json.dumps(report,indent=2)+'\n');print(report)

if __name__=='__main__':main()
