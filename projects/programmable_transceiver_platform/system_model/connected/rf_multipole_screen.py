"""Continuous multipole receive filter with exact event-driven envelope propagation."""
import cmath,json,math
import numpy as np
from scipy import signal
from chip_model import P
from rf_cascade_state import RfCascadeState
from rf_selectivity_screen import butterworth_order
from rf_quality_screen import simulate,quality
from session import Session
from whole_chip_lifecycle import expect_rejection


def controls(order,cutoff):
    a=RfCascadeState(Session());a.set_butterworth(order,cutoff)
    a.rx_route='external_tone';a.external_amplitude=1
    b=RfCascadeState(Session());b.set_butterworth(order,cutoff)
    b.rx_route='external_tone';b.external_amplitude=1
    times=np.linspace(0,20,101)
    numerator,denominator=signal.butter(order,1,analog=True)
    _,expected=signal.step((numerator,denominator),T=times)
    error=0.
    for t,y in zip(times,expected):
        a.advance(float(t)/(2*math.pi*cutoff));error=max(error,abs(a.received-y))
    b.advance(float(times[-1])/(2*math.pi*cutoff))
    assert error<1e-12 and abs(a.received-b.received)<1e-12
    bank=a.rx_bank
    for f in (0,1e6,8e6,10e6,20e6,30e6):
        modal=sum(w*p/(2j*math.pi*f+p) for w,p in zip(bank['weights'],bank['poles']))
        independent=1/math.sqrt(1+(f/cutoff)**(2*order))
        assert abs(abs(modal)-independent)<1e-13
    # Disconnecting the input retains internal state and gives the correct homogeneous tail.
    before=list(bank['states']);a.rx_route='mute';t=a.time;dt=30e-9
    a.advance(t+dt)
    expected=sum(w*x*cmath.exp(-p*dt) for w,x,p in zip(bank['weights'],before,bank['poles']))
    assert abs(a.received-expected)<1e-13
    expect_rejection(lambda:a.set_butterworth(order,cutoff))
    expect_rejection(lambda:a.set_bandwidths(5e6,5e6,a.time))
    return dict(independent_step_max_error=error,subdivision_error=abs(b.received-float(signal.step((numerator,denominator),T=times)[1][-1])))


def main():
    order,cutoff=butterworth_order(8e6,20e6,1,30);checks=controls(order,cutoff);rows=[]
    for mode in (0,1):
        baseline,t,reference=simulate(mode,1,'ideal',rx_filter=(order,cutoff))
        traffic,times,values=simulate(mode,1,'combined',(20e6,30e6),rx_filter=(order,cutoff))
        assert t==times
        rows.append(dict(mode=mode,quality=quality(reference,values),traffic=traffic,
                         reference_adc_sha256=baseline['adc_sha256']))
    report=dict(status='passed',order=order,cutoff_hz=cutoff,controls=checks,cases=rows,
        complete_architecture=False,physical_qualification=False,
        limitations=['Modal states implement an ideal continuous transfer function, not five physically realizable independent complex circuits.',
        'Topology selection is restricted to initial unenergized state; live topology remapping is deliberately rejected.',
        'This test uses the existing two-frequency I/Q waveform, not a full-band modulated wanted signal.',
        'Reference includes the same filter response; filter passband and transient tests are checked independently.',
        'Finite gain-bandwidth, component spread, internal noise and internal overload remain unmodeled.'])
    (P/'evidence/connected-rf-multipole-screen.json').write_text(json.dumps(report,indent=2)+'\n')
    print(checks)
    for r in rows:print(r['mode'],r['quality'])

if __name__=='__main__':main()
