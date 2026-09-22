"""LO projection connected ahead of common-chip filtering and ADC capture."""
import hashlib,json
from pathlib import Path
from chip import TransceiverChip
from shared_tx_traffic import scenario
from lo_drive import iq_projection,square_fixture
from lo_mixer import connect

def main():
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    p=scenario.architecture.P
    files=list(scenario.architecture.D.glob('*.py'))+list(Path(__file__).parent.glob('*.py'))+[p/'verification/stream_codec.py']
    hashes={str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    rows=[]
    for mode in (0,1):
        for period in (8,4):
            projection=iq_projection(*square_fixture(2.4e9,240,period),2.4e9)
            a=TransceiverChip(trim_offsets_v=(0.,0.),watchdog_s=1e-3)
            b=TransceiverChip(trim_offsets_v=(0.,0.),watchdog_s=1e-3)
            connect(b,projection['desired'],projection['image'])
            for c in (a,b):
                c.external_source([.2+.1j],0.,1.,offset_hz=1e6)
                c.configure(mode,0.);c.advance(8e-6)
                c.capture(64,c.time+100e-9)
            errors=[]
            for k in range(1,161):
                at=8e-6+k*25e-9;a.advance(at);b.advance(at)
                expected=projection['desired']*a.tx.received+projection['image']*a.tx.received.conjugate()
                errors.append(abs(b.tx.received-expected))
            assert max(errors)<1e-10
            for c in (a,b):
                c.host_decoder.finish();assert c.host_samples==c.adc_words and len(c.host_samples)==64
            assert a.host_samples!=b.host_samples
            rows.append(dict(mode=mode,missing_i_period_cycles=period,
                filter_projection_max_error=max(errors),image_relative_rms=projection['image_relative_rms'],captured=64))
    assert all(hashlib.sha256((p/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
    (p/'evidence/fast-lo-mixer.json').write_text(json.dumps(dict(status='passed',source_sha256=hashes,cases=rows,
        physical_qualification=False,limitations=['Fundamental-only projection; dropout modulation sidebands and DC feedthrough omitted.',
        'Constant external tone, not multicarrier four-path quality.',
        'Switching coefficients are not calibrated against transistor gate drive.']),indent=2)+'\n')
    print('Common-chip LO image/filter/capture checks passed')
if __name__=='__main__':main()
