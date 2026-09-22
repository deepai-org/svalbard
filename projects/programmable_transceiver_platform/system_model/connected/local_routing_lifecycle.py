"""Bounded atomic RX route/filter/gain selection with independent input fixture."""
import cmath,hashlib,json,math
from chip_model import P,encode_iq
from programmable_filters_lifecycle import FilterChip
from playback_memory_lifecycle import ready
from whole_chip_lifecycle import expect_rejection
from rf_cascade_state import RfCascadeState
from session import Session

class RoutedChip(FilterChip):
    def __init__(self,**kwargs):
        super().__init__(**kwargs);self.rx_gain=1.
    def configure_rx(self,route,gain,tx_hz,rx_hz,amplitude=0j,frequency_hz=0):
        if self.session.armed:raise ValueError('Routing configuration requires disarmed state')
        if route not in ('loopback','external_tone','mute') or gain not in (.5,1,2):raise ValueError('Unsupported route/gain')
        if tx_hz not in self.BANDWIDTHS or rx_hz not in self.BANDWIDTHS:raise ValueError('Unsupported filters')
        if not all(math.isfinite(v) for v in (complex(amplitude).real,complex(amplitude).imag,frequency_hz)):
            raise ValueError('Nonfinite source')
        # Validate every field before touching filter state or configuration.
        self.tx.set_bandwidths(tx_hz,rx_hz,self.time)
        self.tx.rx_route=route;self.tx.external_amplitude=complex(amplitude)
        self.tx.external_frequency=frequency_hz;self.rx_gain=gain
    def configure_rf_input(self,blockers=(),cubic=0.,envelope_limit=1.):
        """Weakly nonlinear RF envelope x+cubic*x*|x|^2 before mixing/filtering."""
        if self.session.armed:raise ValueError('RF configuration requires disarmed state')
        tones=tuple((complex(a),float(f)) for a,f in blockers)
        values=[cubic,envelope_limit]+[v for a,f in tones for v in (a.real,a.imag,f)]
        if not all(math.isfinite(v) for v in values) or envelope_limit<=0:
            raise ValueError('Invalid RF input model')
        if len(tones)>4 or abs(cubic)*envelope_limit**2>.25:
            raise ValueError('RF polynomial exceeds declared weak-nonlinearity range')
        self.tx.advance(self.time)
        self.tx.rf_blockers=tones;self.tx.rf_cubic=cubic;self.tx.rf_envelope_limit=envelope_limit
    def configure_lo(self,tx_offset_hz=0.,rx_offset_hz=0.,tx_phase_rad=0.,rx_phase_rad=0.):
        """Offsets from a shared nominal RF carrier; ideal complex mixers."""
        values=(tx_offset_hz,rx_offset_hz,tx_phase_rad,rx_phase_rad)
        if self.session.armed:raise ValueError('LO configuration requires disarmed state')
        if not all(math.isfinite(v) for v in values):raise ValueError('Nonfinite LO setting')
        self.tx.advance(self.time)
        (self.tx.tx_lo_hz,self.tx.rx_lo_hz,self.tx.tx_lo_phase,self.tx.rx_lo_phase)=values
    def receiver_value(self):return self.rx_gain*super().receiver_value()


def controls():
    s=Session();a=RfCascadeState(s);b=RfCascadeState(s)
    for f in (a,b):f.rx_route='external_tone';f.external_amplitude=.3+.1j;f.external_frequency=3e6
    t=73e-9;a.advance(t)
    for i in range(1,101):b.advance(t*i/100)
    pole=a.rx_pole;omega=2*math.pi*3e6
    expected=(.3+.1j)*pole/(pole+1j*omega)*(cmath.exp(1j*omega*t)-math.exp(-pole*t))
    assert abs(a.received-expected)<1e-14 and abs(a.received-b.received)<1e-14
    c=RoutedChip();old=(c.rx_gain,c.tx.pole,c.tx.rx_route)
    expect_rejection(lambda:c.configure_rx('mute',2,3e6,10e6))
    assert old==(c.rx_gain,c.tx.pole,c.tx.rx_route)


def run(mode,route,gain):
    c=RoutedChip(watchdog_s=20e-6)
    c.configure_rx(route,gain,5e6,10e6,.2+.1j,1e6)
    bits=12 if mode==0 else 8
    for i in range(32):c.write_playback(i,encode_iq(.5 if i%2 else -.25,bits))
    c.select_playback(True);ready(c,mode)
    expect_rejection(lambda:c.configure_rx('mute',1,10e6,10e6))
    start=c.time+100e-9;c.schedule(32,start);c.capture(32,start+10e-9)
    c.advance(start+32*c.period+2e-6);c.host_decoder.finish()
    assert c.host_samples==c.adc_words and len(c.adc_words)==32
    if route=='mute':assert not any(c.adc_words)
    else:assert any(c.adc_words)
    return dict(mode=mode,route=route,gain=gain,adc_sha256=hashlib.sha256(json.dumps(c.adc_words).encode()).hexdigest())


def main():
    controls();rows=[run(m,r,g) for m in (0,1) for r in ('loopback','external_tone','mute') for g in (.5,2)]
    for mode in (0,1):
        for route in ('loopback','external_tone'):
            assert len({r['adc_sha256'] for r in rows if r['mode']==mode and r['route']==route})==2
    report=dict(status='passed',cases=rows,complete_architecture=False,physical_qualification=False,
        limitations=['External tone is an ideal downconverted envelope fixture, not a physical RF source or complete mixer/LO model.',
        'Loopback denotes the existing external channel fixture, not an added silicon RF connection.',
        'Gain is a linear local baseband setting; no gain-bandwidth/noise tradeoff is implied.',
        'Three exclusive receive selections do not yet implement the full intended programmable resource graph.'])
    (P/'evidence/connected-local-routing.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed12 local route/gain cases and analytic/atomicity controls')

if __name__=='__main__':main()
