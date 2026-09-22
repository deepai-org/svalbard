"""Independent ideal RF oscillators, exact envelope mixing before RX filtering."""
import cmath, hashlib, json, math
from chip_model import P, encode_iq
from local_routing_lifecycle import RoutedChip
from playback_memory_lifecycle import ready
from rf_cascade_state import RfCascadeState
from session import Session
from whole_chip_lifecycle import expect_rejection


def controls():
    errors=[]
    for offset in (-25e6,-1e6,0,1e6,25e6):
        a=RfCascadeState(Session());b=RfCascadeState(Session())
        for c in (a,b):
            c.held=.3+.2j;c.filtered=-.1+.05j;c.received=.07j
            c.tx_lo_hz=offset;c.tx_lo_phase=.4;c.rx_lo_phase=-.2
            c.rx_pole=c.pole*(1+1e-10)
        t=73e-9;initial=a.received;held=a.held;x=a.filtered
        # Independent midpoint quadrature of the physical envelope ODE integral.
        n=40000;dt=t/n;total=0j
        for i in range(n):
            u=(i+.5)*dt
            value=held+(x-held)*math.exp(-a.pole*u)
            total+=a.rx_pole*math.exp(-a.rx_pole*(t-u))*value*cmath.exp(1j*(2*math.pi*offset*u+.6))*dt
        expected=initial*math.exp(-a.rx_pole*t)+total
        a.advance(t)
        for i in range(1,101):b.advance(t*i/100)
        assert abs(a.received-expected)<2e-9
        assert abs(a.received-b.received)<1e-13
        errors.append(abs(a.received-expected))
    # Common-mode LO cancels in loopback, but not for an independent external source.
    a=RfCascadeState(Session());b=RfCascadeState(Session())
    for c in (a,b):c.held=.3;c.filtered=.3
    b.tx_lo_hz=b.rx_lo_hz=12e6;b.tx_lo_phase=b.rx_lo_phase=.7
    a.advance(1e-6);b.advance(1e-6);assert a.received==b.received
    for c in (a,b):c.rx_route='external_tone';c.external_amplitude=.3
    a.advance(2e-6);b.advance(2e-6)
    assert abs(a.received-b.received)>.1
    c=RoutedChip();before=(c.tx.tx_lo_hz,c.tx.rx_lo_hz)
    expect_rejection(lambda:c.configure_lo(1,float('nan')))
    assert before==(c.tx.tx_lo_hz,c.tx.rx_lo_hz)
    # A large mismatch is a signal-quality failure, not automatically a digital fault.
    ratios=[]
    for offset in (0,1e6,25e6):
        s=RfCascadeState(Session());s.held=s.filtered=.3;s.tx_lo_hz=offset;s.rx_pole=2*math.pi*2e6
        s.advance(3e-6);ratio=abs(s.received)/.3
        expected=1/math.sqrt(1+(offset/2e6)**2)
        assert abs(ratio-expected)<1e-12
        ratios.append(ratio)
    assert ratios[1]>.89 and ratios[2]<.08
    return dict(quadrature_max_error=max(errors),mismatch_amplitude_ratios=ratios)


def run(mode,offset,phase):
    c=RoutedChip(watchdog_s=20e-6)
    c.configure_rx('loopback',1,5e6,2e6)
    c.configure_lo(offset,0,phase,0)
    bits=12 if mode==0 else 8
    for i in range(32):c.write_playback(i,encode_iq(.3+.1j,bits))
    c.select_playback(True);ready(c,mode)
    expect_rejection(lambda:c.configure_lo())
    start=c.time+100e-9;c.schedule(32,start);c.capture(32,start+10e-9)
    c.advance(start+32*c.period+2e-6);c.host_decoder.finish()
    assert len(c.adc_words)==32 and c.host_samples==c.adc_words
    assert c.tx.accounting()['consumed']==32
    return dict(mode=mode,offset_hz=offset,phase_rad=phase,
                adc_sha256=hashlib.sha256(json.dumps(c.adc_words).encode()).hexdigest())


def main():
    checks=controls()
    rows=[run(m,f,p) for m in (0,1) for f,p in ((0,0),(0,.5),(-1e6,0),(1e6,0),(25e6,0))]
    for mode in (0,1):assert len({r['adc_sha256'] for r in rows if r['mode']==mode})==5
    report=dict(status='passed',controls=checks,cases=rows,complete_architecture=False,physical_qualification=False,
        limitations=['Ideal complex mixers omit images, LO leakage, RF compression and blockers.',
        'Offsets are relative to a common nominal carrier; absolute RF device bandwidth is not qualified.',
        'Oscillators are constant-frequency and independent of sample PLL; phase noise and supply response remain open.',
        'No carrier recovery or modem is on chip; attenuation control is not a Wi-Fi compliance threshold.',
        'Integrated scenarios are finite playback/capture, not sustained simultaneous wired traffic.'])
    (P/'evidence/connected-rf-lo-lifecycle.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed10 integrated RF LO cases, quadrature/subdivision, cancellation and mismatch controls')

if __name__=='__main__':main()
