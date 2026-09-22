"""Failure-path controls for the actual host calibration preparation callback."""
import json
from types import SimpleNamespace
from unittest.mock import patch
from chip_model import P
from managed_tx_quality import calibration_window

class TransportFixture:
    def __init__(self,ready_after=0,reject=None,sequence_ready=True,transaction_s=12.85e-6):
        self.time=0.;self.calls=[];self.transaction_s=transaction_s;self.ready_after=ready_after;self.reject=reject
        self.sequence_ready=sequence_ready;self.tx_cal=SimpleNamespace(state='idle')
    def advance(self,t):
        assert t>=self.time;self.time=t
        if self.tx_cal.state=='settle' and self.sequence_ready:self.tx_cal.state='ready'
    def command(self,c,op,payload=0):
        assert c is self
        self.time+=self.transaction_s;self.calls.append(op)
        if self.reject==op:return dict(accepted=False,reason='injected execution-time rejection')
        if op=='tx_cal_status':return dict(accepted=True,value=(1<<10) if self.time>=self.ready_after else 0)
        if op=='tx_cal_start':self.tx_cal.state='settle';return dict(accepted=True,value=7)
        if op=='tx_cal_commit':
            assert payload==7 and self.tx_cal.state=='ready'
            self.tx_cal.state='done';return dict(accepted=True)
        raise AssertionError(op)

def run(c):
    with patch('managed_tx_quality.command',c.command):calibration_window(False)(c)

def main():
    cases=[]
    for delay in (0,25e-6,50e-6):
        c=TransportFixture(ready_after=delay)
        try:run(c)
        except TimeoutError:
            # A late ready reply can leave too little time for calibration itself.
            assert delay==50e-6 and c.time>100e-6
            cases.append(dict(name='late readiness exceeds total budget',time_s=c.time,calls=c.calls))
        else:
            assert c.time==100e-6 and c.tx_cal.state=='done'
            cases.append(dict(name='ready',delay_s=delay,time_s=c.time,calls=c.calls))
    slow=TransportFixture(ready_after=50e-6,transaction_s=17e-6)
    try:run(slow)
    except TimeoutError:pass
    else:raise AssertionError('Total preparation deadline must reject slow transport')
    assert slow.time>100e-6
    cases.append(dict(name='slow transport budget exceeded',time_s=slow.time,calls=slow.calls))
    c=TransportFixture(ready_after=float('inf'))
    try:run(c)
    except TimeoutError:pass
    else:raise AssertionError('Missing readiness must time out')
    assert c.calls==['tx_cal_status']*4 and c.time<63e-6
    cases.append(dict(name='no readiness',time_s=c.time,calls=c.calls))
    for op in ('tx_cal_start','tx_cal_commit'):
        c=TransportFixture(reject=op)
        try:run(c)
        except AssertionError:pass
        else:raise AssertionError('Rejected command must stop preparation')
        assert c.calls[-1]==op
        cases.append(dict(name='reject '+op,calls=c.calls))
    c=TransportFixture(sequence_ready=False)
    try:run(c)
    except AssertionError:pass
    else:raise AssertionError('Unfinished fit must not commit')
    assert 'tx_cal_commit' not in c.calls
    report=dict(status='passed',cases=cases,limitations=['Synthetic serialized transport exercises host policy only; full chip lock/noise behavior checked separately.',
        'Late readiness can complete calibration before overall budget rejection; no traffic is activated, but this is not rollback.'])
    (P/'evidence/connected-tx-preparation-policy.json').write_text(json.dumps(report,indent=2)+'\n');print(report)
if __name__=='__main__':main()
