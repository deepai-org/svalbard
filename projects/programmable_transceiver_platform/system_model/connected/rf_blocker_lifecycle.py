"""Pre-filter weak RF nonlinearity, blockers and intermodulation controls."""
import cmath,json,math,hashlib
from chip_model import P,encode_iq
from local_routing_lifecycle import RoutedChip
from playback_memory_lifecycle import ready
from rf_cascade_state import RfCascadeState
from session import Session
from sustained_lifecycle import run as sustained_run
from whole_chip_lifecycle import expect_rejection


def state(alpha):
    s=RfCascadeState(Session());s.rx_route='external_tone';s.external_amplitude=.05
    s.rf_blockers=((.3,10e6),(.2,20e6));s.rf_cubic=alpha;s.rf_envelope_limit=1.
    s.rx_pole=2*math.pi*2e6
    return s


def controls():
    errors=[];dc=[]
    for alpha in (-.2,0,.2):
        a=state(alpha);b=state(alpha);t=83e-9;n=40000;dt=t/n
        total=0j
        for i in range(n):
            u=(i+.5)*dt;x=.05+.3*cmath.exp(2j*math.pi*10e6*u)+.2*cmath.exp(2j*math.pi*20e6*u)
            total+=a.rx_pole*math.exp(-a.rx_pole*(t-u))*(x+alpha*x*abs(x)**2)*dt
        a.advance(t)
        for i in range(1,101):b.advance(t*i/100)
        assert abs(a.received-total)<2e-9 and abs(a.received-b.received)<1e-13
        errors.append(abs(a.received-total))
        # No desired signal: two out-of-band tones create a DC intermodulation term.
        c=state(alpha);c.external_amplitude=0
        samples=[]
        for i in range(100):c.advance(5e-6+i/100e6);samples.append(c.received)
        mean=sum(samples)/len(samples);expected=alpha*.3**2*.2
        assert abs(mean-expected)<1e-13
        dc.append(mean.real)
    assert dc[0]<0 and abs(dc[1])<1e-13 and dc[2]>0
    # Range violation must not silently extrapolate cubic behavior into saturation.
    c=state(-.2);c.external_amplitude=1
    expect_rejection(lambda:c.advance(1e-9));assert c.time==0 and c.received==0
    c=RoutedChip();expect_rejection(lambda:c.configure_rf_input(cubic=-1))
    assert c.tx.rf_cubic==0
    # Exact cascade expansion also covers moving TX-filter state and LO offsets.
    a=state(-.2);b=state(-.2)
    for c in (a,b):
        c.rx_route='loopback';c.held=.2;c.filtered=-.1j;c.tx_lo_hz=1e6;c.rx_lo_hz=-.5e6
    a.advance(t)
    for i in range(1,101):b.advance(t*i/100)
    assert abs(a.received-b.received)<1e-13
    return dict(quadrature_max_error=max(errors),in_band_intermodulation_dc=dc)


def run(mode,alpha):
    c=RoutedChip(watchdog_s=20e-6)
    c.configure_rx('loopback',1,5e6,2e6)
    c.configure_rf_input(((.3,10e6),(.2,20e6)),alpha)
    bits=12 if mode==0 else 8
    for i in range(32):c.write_playback(i,encode_iq(.05,bits))
    c.select_playback(True);ready(c,mode)
    expect_rejection(lambda:c.configure_rf_input())
    start=c.time+100e-9;c.schedule(32,start);c.capture(32,start+10e-9)
    c.advance(start+32*c.period+2e-6);c.host_decoder.finish()
    assert len(c.adc_words)==32 and c.host_samples==c.adc_words and c.tx.consumed==32
    return dict(mode=mode,cubic=alpha,adc_sha256=hashlib.sha256(json.dumps(c.adc_words).encode()).hexdigest())


def main():
    checks=controls();rows=[run(m,a) for m in (0,1) for a in (-.2,0,.2)]
    for mode in (0,1):assert len({r['adc_sha256'] for r in rows if r['mode']==mode})==3
    sustained=[]
    for mode in (0,1):
        for alpha in (-.05,.05):
            def factory(**kwargs):
                c=RoutedChip(**kwargs)
                c.configure_rf_input(((.1,10e6),(.1,20e6)),alpha,envelope_limit=1.5)
                return c
            row=sustained_run(mode,100,chip_factory=factory,disturbance_sign=1,matched_reference=True,host_ppm=-100)
            row['rf_cubic']=alpha;sustained.append(row)
        assert sustained[-1]['adc_sha256']!=sustained[-2]['adc_sha256']
    report=dict(status='passed',controls=checks,cases=rows,sustained_cases=sustained,complete_architecture=False,physical_qualification=False,
        limitations=['Cubic RF envelope is bounded weak nonlinearity, not an overload/saturation or physical IIP3 model.',
        'At most four blocker tones; envelope units and coefficients are explicit uncalibrated assumptions.',
        'Complex-envelope mixer omits images, LO leakage and RF frequency-dependent gain.',
        'Range violations stop simulation explicitly; they do not yet map to chip fault telemetry.',
        'ADC sampling follows analog filtering, but comprehensive alias/noise/blocker envelopes remain open.'])
    (P/'evidence/connected-rf-blocker-lifecycle.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed four sustained and six finite integrated RF blocker cases and quadrature, intermodulation, range and subdivision controls')

if __name__=='__main__':main()
