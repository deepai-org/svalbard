"""Disarmed local filter selection, state preservation and integrated response."""
import json,math,hashlib
from chip_model import P,encode_iq
from playback_memory_lifecycle import PlaybackChip,ready
from whole_chip_lifecycle import expect_rejection
from rf_cascade_state import RfCascadeState,controls as old_controls
from session import Session

class FilterChip(PlaybackChip):
    BANDWIDTHS=(2e6,5e6,10e6,20e6)
    def configure_filters(self,tx_hz,rx_hz):
        if self.session.armed:raise ValueError('Filter configuration requires disarmed state')
        if tx_hz not in self.BANDWIDTHS or rx_hz not in self.BANDWIDTHS:
            raise ValueError('Unsupported filter selection')
        self.tx.set_bandwidths(tx_hz,rx_hz,self.time)


def controls():
    old_controls()
    for tx,rx in [(2e6,20e6),(20e6,2e6),(10e6,10e6*(1+1e-10))]:
        s=Session();s.configure(0);s.host_ready=True;s.ready.update(rf=True,wire=True);s.arm()
        x=RfCascadeState(s);y=RfCascadeState(s)
        for f in (x,y):f.set_bandwidths(tx,rx,0);f.accept(1);f.clock(0)
        t=40e-9;x.advance(t)
        for i in range(1,101):y.advance(t*i/100)
        assert abs(x.received-y.received)<1e-13
        a,b=2*math.pi*tx,2*math.pi*rx
        if abs(tx-rx)>1:
            expected=1-(b*math.exp(-a*t)-a*math.exp(-b*t))/(b-a)
            assert abs(x.received-expected)<1e-14
        else:
            expected=1-(1+a*t)*math.exp(-a*t)
            assert abs(x.received-expected)<1e-10
        before=(x.filtered,x.received)
        x.set_bandwidths(5e6,10e6,t)
        assert (x.filtered,x.received)==before


def run(mode,tx,rx):
    c=FilterChip(watchdog_s=20e-6);c.configure_filters(tx,rx)
    expect_rejection(lambda:c.configure_filters(3e6,10e6))
    bits=12 if mode==0 else 8
    for i in range(32):c.write_playback(i,encode_iq(complex(.5 if i%4<2 else -.5,.25),bits))
    c.select_playback(True);ready(c,mode)
    expect_rejection(lambda:c.configure_filters(5e6,5e6))
    start=c.time+100e-9;c.schedule(32,start);c.capture(32,start+10e-9)
    c.advance(start+32*c.period+2e-6);c.host_decoder.finish()
    assert c.host_samples==c.adc_words and len(c.adc_words)==32
    assert [c.capture_bank.read(i) for i in range(32)]==c.adc_words
    return dict(mode=mode,tx_bandwidth_hz=tx,rx_bandwidth_hz=rx,
                adc_sha256=hashlib.sha256(json.dumps(c.adc_words).encode()).hexdigest())

def main():
    controls();rows=[run(m,tx,rx) for m in (0,1) for tx,rx in ((10e6,10e6),(2e6,20e6),(5e6,2e6))]
    for mode in (0,1):assert len({r['adc_sha256'] for r in rows if r['mode']==mode})==3
    report=dict(status='passed',cases=rows,complete_architecture=False,physical_qualification=False,
        limitations=['Four bandwidth settings are candidate functional selections, not verified transistor tuning ranges.',
        'First-order continuous filters only; tuning parasitics/noise and switch charge injection are omitted.',
        'Control is coherent and disarmed; SPI/CDC and generic routing remain separate work.'])
    (P/'evidence/connected-programmable-filters.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed six filter-selection cases and unequal/near-equal-pole controls')

if __name__=='__main__':main()
