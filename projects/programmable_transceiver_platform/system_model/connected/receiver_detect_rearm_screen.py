"""Explicit recovery after abort without erasing capacitor state or stale results."""
import json,hashlib,math
from pathlib import Path
from receiver_detect_probe_sequence import Probe,load,reject

class RecoverableProbe(Probe):
    def __init__(self,loads):
        super().__init__(loads);self.recovering=False
    def rearm(self,time,epoch,tx_busy=False):
        if tx_busy or epoch!=self.epoch or self.state not in ('aborted','fault'):
            raise ValueError('Recovery ownership/epoch conflict')
        if not math.isfinite(time) or time<self.time:raise ValueError('Invalid recovery time')
        self.advance(time)
        self.pending=None;self.result=None;self.samples=[[],[]];self.recovering=True
        self.state='releasing';self.drive=0.;self.release_start=time;self.next_event=time+1e-6
    def advance(self,time):
        super().advance(time)
        if self.recovering and self.state=='ready':
            # Settling after abort is not a completed detection result.
            self.result=None;self.state='idle';self.recovering=False
    def abort(self,time):
        super().abort(time);self.recovering=False


def main():
    fresh=RecoverableProbe([load(75.),load(75.)]);fresh.abort(0.)
    fresh.rearm(0.,fresh.epoch);fresh.advance(20e-6)
    assert fresh.state=='idle' and fresh.result is None
    rows=[]
    for terms,expected in [((75.,75.),'present'),((1e8,1e8),'absent'),((75.,1e8),'indeterminate')]:
        for stop in (73e-9,205e-9):
            p=RecoverableProbe([load(r) for r in terms]);p.start(0,0);p.advance(stop)
            before=[leg.x.copy() for leg in p.legs];p.abort(stop)
            assert all((x==leg.x).all() for x,leg in zip(before,p.legs))
            assert p.drive is None and p.epoch==1
            reject(lambda:p.start(stop,1));reject(lambda:p.rearm(stop,0));reject(lambda:p.rearm(stop,1,True))
            p.rearm(stop,1)
            assert all((x==leg.x).all() for x,leg in zip(before,p.legs))
            reject(lambda:p.start(stop,1));reject(lambda:p.read(1))
            # Interruption of recovery again disconnects without silently completing.
            p.advance(stop+200e-9);p.abort(p.time);assert p.epoch==2 and p.drive is None
            reject(lambda:p.rearm(p.time,1));p.rearm(p.time,2)
            p.advance(p.time+20e-6)
            assert p.state=='idle' and p.result is None and p.drive is None
            assert max(abs(v) for leg in p.legs for v in leg.x)<=.005
            reject(lambda:p.read(2));p.start(p.time,2);p.advance(p.time+10e-6)
            result=p.read(2);assert result['decision']==expected
            reject(lambda:p.read(0));reject(lambda:p.read(1))
            rows.append(dict(terms_ohm=terms,abort_time_s=stop,new_epoch=2,result=result))
    report=dict(status='passed',connected=False,physical_qualification=False,cases=rows,
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        dependency_hashes={n:hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest() for n in ('receiver_detect_probe_sequence.py','receiver_detect_release_screen.py','receiver_detect_load_screen.py')},
        limitations=['Standalone state-machine tests; chip reset/reference callbacks, TX exclusion and management transport are not connected yet.',
        'Only selected loads; no joint recovery sensor-error envelope or analog driver qualification.',
        'Explicit active rearm introduces source/sink loading which still must enter the shared-rail model.'])
    (Path(__file__).resolve().parents[2]/'evidence/receiver-detect-rearm-screen.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed six abort/rearm cases including interrupted recovery and stale-result rejection')

if __name__=='__main__':main()
