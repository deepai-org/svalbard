"""Late substep failure cannot leave the driver and PLL at different times."""
import json,pickle
from chip_model import P
from rf_driver_transient import CoupledDriver
from pulse_clock_service import PulseClockService
from driver_pll_feedback import advance_feedback

class FailsLate(CoupledDriver):
    def advance(self,time,*args,**kwargs):
        if time>2e-9:raise ValueError('Injected late integration failure')
        return super().advance(time,*args,**kwargs)

def main():
    d=FailsLate();p=PulseClockService(40e6,60,2.4e9)
    before=pickle.dumps((d,p));network=d.network
    try:advance_feedback(d,p,5e-9,[(.2+0j,0j)],1e6,1e-9)
    except ValueError as e:assert str(e)=='Injected late integration failure'
    else:raise AssertionError('Expected integration failure')
    assert pickle.dumps((d,p))==before and d.network is network
    good=CoupledDriver();clock=PulseClockService(40e6,60,2.4e9);network=good.network
    advance_feedback(good,clock,2e-9,[(.2+0j,0j)],1e6,1e-9)
    assert good.time==clock.time==2e-9 and good.network is network
    report=dict(status='passed',checks=['late failure leaves all original state unchanged','success commits aligned clocks','network identity retained'],
        limitations=['Local failure-injection boundary; not whole-chip fault/recovery qualification.'])
    (P/'evidence/connected-driver-feedback-transaction.json').write_text(json.dumps(report,indent=2)+'\n');print(report)

if __name__=='__main__':main()
