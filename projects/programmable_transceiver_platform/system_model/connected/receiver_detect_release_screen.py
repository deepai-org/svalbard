"""Persistent capacitor state, source disconnection and repeated load probes."""
import json,hashlib,itertools
from pathlib import Path
import numpy as np
from scipy.linalg import expm
from receiver_detect_load_screen import matrices,classify

class Leg:
    def __init__(self,params,leakage=1e6):
        self.p=dict(params);self.leakage=leakage;self.x=np.zeros(2);self.time=0.
        self.C,_,_=matrices(**params)
    def advance(self,time,drive):
        if not np.isfinite(time) or time<self.time:raise ValueError('Invalid time')
        if drive is not None and not np.isfinite(drive):raise ValueError('Invalid source')
        g=1/self.leakage+(1/self.p['rs'] if drive is not None else 0.)
        G=np.diag([g,1/self.p['rt']]);A=-np.linalg.solve(self.C,G)
        eq=np.array([(drive/self.p['rs']/g) if drive is not None else 0.,0.])
        self.x=eq+expm(A*(time-self.time))@(self.x-eq);self.time=time
    def probe(self):
        start=self.time;baseline=self.x[0];values=[]
        for t in (100e-9,200e-9):
            self.advance(start+t,.2);values.append(float((self.x[0]-baseline)/.2))
        return dict(samples=values,result=classify(values))


def main():
    rows=[];repeat_failures=[]
    for rt,cc,rs in itertools.product((40.,100.,1e5,1e8),(10e-9,100e-9),(100.,1000.)):
        p=dict(cp=5e-12,cr=5e-12,cc=cc,rs=rs,rt=rt)
        a=Leg(p);first=a.probe();expected='present' if rt<=100 else 'absent'
        assert first['result']==expected
        # Passive disconnection retains both capacitor voltages.
        state=a.x.copy();a.advance(a.time,None);assert np.array_equal(state,a.x)
        a.advance(a.time+1e-6,None);second=a.probe()
        if second['result']!=expected:repeat_failures.append(dict(parameters=p,result=second))
        # Candidate active return-to-baseline, then high impedance. This is an
        # explicit driver operation, never an assignment of capacitor voltages.
        release_start=a.time;steps=0
        while max(abs(a.x))>.005 and steps<1000:
            a.advance(a.time+1e-6,0.);steps+=1
        assert max(abs(a.x))<=.005
        release_s=a.time-release_start
        a.advance(a.time+1e-6,None);third=a.probe()
        assert third['result']==expected,(p,third)
        # Independent caller subdivision, including during an interrupted pulse.
        b=Leg(p);c=Leg(p);b.advance(73e-9,.2)
        for t in np.linspace(0,73e-9,101)[1:]:c.advance(float(t),.2)
        b.advance(8e-6,None);c.advance(8e-6,None)
        error=float(max(abs(b.x-c.x)));assert error<1e-10
        rows.append(dict(parameters=p,first=first,passive_repeat=second,
            active_release_s=release_s,after_active_release=third,subdivision_error_v=error))
    assert repeat_failures
    report=dict(status='passed',connected=False,physical_qualification=False,cases=rows,
        passive_repeat_failures=repeat_failures,maximum_active_release_s=max(r['active_release_s'] for r in rows),
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        dependency_sha256=hashlib.sha256(Path(__file__).with_name('receiver_detect_load_screen.py').read_bytes()).hexdigest(),
        limitations=['Sixteen selected load cases; no full uncertainty/sensor sweep on repeated probes.',
        'Active discharge is an added candidate operation requiring a real TX common-mode driver and current/supply budget.',
        'Abort disconnects the source and retains state; no silent voltage reset or immediate readiness is implied.',
        'No connected chip scheduler, two-leg sequencing or protocol qualification yet.'])
    (Path(__file__).resolve().parents[2]/'evidence/receiver-detect-release-screen.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Cases',len(rows),'passive repeat failures',len(repeat_failures),'max active release',report['maximum_active_release_s'])

if __name__=='__main__':main()
