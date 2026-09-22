"""Causal piecewise RF oscillator trajectories; phase steps and frequency changes."""
from collections import deque
import cmath,json,math,random
from chip_model import P
from local_routing_lifecycle import RoutedChip
from rf_cascade_state import RfCascadeState
from session import Session
from sustained_lifecycle import run
from whole_chip_lifecycle import expect_rejection


def change_lo(state,time,tx_phase=0.,rx_phase=0.,tx_frequency=0.,rx_frequency=0.):
    """Frequency changes preserve instantaneous phase except explicit phase steps."""
    values=(time,tx_phase,rx_phase,tx_frequency,rx_frequency)
    if not all(math.isfinite(v) for v in values) or time<state.time:
        raise ValueError('Invalid RF oscillator intervention')
    state.advance(time)
    state.tx_lo_phase+=tx_phase-2*math.pi*tx_frequency*time
    state.rx_lo_phase+=rx_phase-2*math.pi*rx_frequency*time
    state.tx_lo_hz+=tx_frequency;state.rx_lo_hz+=rx_frequency


class PhaseChip(RoutedChip):
    def __init__(self,**kwargs):
        super().__init__(**kwargs);self.lo_events=deque();self.lo_history=[]
    def schedule_lo(self,events):
        if self.session.armed:raise ValueError('Schedule RF disturbances while disarmed')
        rows=[tuple(row) for row in events]
        previous=self.time
        for row in rows:
            if len(row)!=5 or not all(math.isfinite(v) for v in row) or row[0]<=previous:
                raise ValueError('RF events require finite strictly increasing future times')
            previous=row[0]
        self.lo_events=deque(rows)
    def advance(self,time):
        while self.lo_events and self.lo_events[0][0]<=time:
            event=self.lo_events.popleft()
            # Existing ADC/DAC events at exactly this time execute before intervention.
            super().advance(event[0])
            before=self.tx.received
            change_lo(self.tx,*event)
            assert self.tx.received==before
            self.lo_history.append(dict(time=event[0],tx_phase_step=event[1],rx_phase_step=event[2],
                                        tx_frequency_step=event[3],rx_frequency_step=event[4]))
        super().advance(time)
    def reference_metrics(self):
        result=super().reference_metrics();result['rf_lo_events']=list(self.lo_history)
        return result


def trace(shared,seed=800):
    # Seeded bounded phase samples, represented by jumps on a declared 100ns grid.
    rng=random.Random(seed);previous_tx=previous_rx=0.;rows=[]
    for i in range(151):
        tx=rng.uniform(-.15,.15);rx=tx if shared else rng.uniform(-.15,.15)
        rows.append((5e-6+i*100e-9,tx-previous_tx,rx-previous_rx,0.,0.))
        previous_tx,previous_rx=tx,rx
    return rows


def controls():
    s=RfCascadeState(Session());s.held=s.filtered=.3
    s.advance(1e-6);before=s.received
    change_lo(s,1e-6,rx_phase=.3,rx_frequency=1e6)
    assert s.received==before
    assert abs(2*math.pi*s.rx_lo_hz*1e-6+s.rx_lo_phase-.3)<1e-14
    dt=73e-9;s.advance(1e-6+dt)
    omega=-2*math.pi*1e6;b=s.rx_pole
    expected=before*math.exp(-b*dt)+.3*cmath.exp(-.3j)*b/(b+1j*omega)*(cmath.exp(1j*omega*dt)-math.exp(-b*dt))
    assert abs(s.received-expected)<1e-14
    expect_rejection(lambda:change_lo(s,0))
    c=PhaseChip();c.schedule_lo([(1e-6,0,0,0,0)])
    old=list(c.lo_events)
    expect_rejection(lambda:c.schedule_lo([(2e-6,0,0,0,0),(1e-6,0,0,0,0)]))
    assert list(c.lo_events)==old
    # Event subdivision must not alter continuous filter evolution.
    a=PhaseChip();b=PhaseChip()
    for c in (a,b):
        c.tx.held=c.tx.filtered=.3
        c.schedule_lo([(1e-6,.1,-.2,1e6,-1e6),(2e-6,-.1,.2,-1e6,1e6)])
    a.advance(3e-6)
    for i in range(1,301):b.advance(i*10e-9)
    assert abs(a.tx.received-b.tx.received)<1e-13 and len(a.lo_history)==2
    return dict(analytic_phase_frequency_error=abs(s.received-expected),subdivision_error=abs(a.tx.received-b.tx.received))


def main():
    checks=controls();rows=[]
    for mode in (0,1):
        baseline=run(mode,100,chip_factory=PhaseChip,matched_reference=True,host_ppm=-100)
        for shared in (True,False):
            def factory(**kwargs):
                c=PhaseChip(**kwargs);c.schedule_lo(trace(shared));return c
            row=run(mode,100,chip_factory=factory,matched_reference=True,host_ppm=-100)
            assert len(row['reference_metrics']['rf_lo_events'])==151
            if shared:assert row['adc_sha256']==baseline['adc_sha256']
            else:assert row['adc_sha256']!=baseline['adc_sha256']
            row['shared_lo_phase']=shared;rows.append(row)
    combined=[]
    for mode in (0,1):
        for sign in (-1,1):
            def factory(**kwargs):
                c=PhaseChip(coupling_per_v=sign,return_charge_per_transition=50e-15,
                    dac_coupling_per_v=sign,frontend=dict(gain_error=sign*.03,
                    phase_error=sign*.03,saturation=.8,noise_rms=.001,seed=800),**kwargs)
                c.configure_rf_input(((.1,10e6),(.1,20e6)),sign*.05,envelope_limit=1.5)
                c.schedule_lo(trace(False));return c
            row=run(mode,100,chip_factory=factory,matched_reference=True,host_ppm=-100,
                    disturbance_sign=sign,service_pauses={48:16})
            assert len(row['reference_metrics']['rf_lo_events'])==151
            row['impairment_sign']=sign;combined.append(row)
    report=dict(status='passed',controls=checks,cases=rows,combined_cases=combined,complete_architecture=False,physical_qualification=False,
        limitations=['Bounded seeded piecewise phase trajectory is a sensitivity fixture, not calibrated phase-noise PSD or jitter.',
        'Ideal zero-delay loopback cancels common LO phase; external blockers, propagation delay and independent RF sources do not generally cancel.',
        'No autonomous RF PLL acquisition, supply-to-LO transfer or physical oscillator model yet.',
        'Coincident sampling precedes the phase event; filter state is continuous and future mixing changes causally.'])
    (P/'evidence/connected-rf-phase-lifecycle.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed four combined-impairment cases, four sustained RF phase cases, two baselines and causal analytic/subdivision controls')

if __name__=='__main__':main()
