"""Independent Fourier/filter quadrature and chip ADC integration checks."""
import cmath,hashlib,json,math
from pathlib import Path
from types import SimpleNamespace
from scipy.integrate import quad_vec
from chip import TransceiverChip
from shared_tx_traffic import scenario
from lo_drive import square_fixture,iq_projection,iq_sidebands
from lo_mixer import connect
from rf_cascade_state import RfCascadeState
from tx_reconstruction import Reconstruction
from session import Session

def main():
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    p=scenario.architecture.P
    files=list(scenario.architecture.D.glob('*.py'))+list(Path(__file__).parent.glob('*.py'))+[p/'verification/stream_codec.py']
    hashes={str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    # Low carrier makes the independently integrated sidebands inexpensive.
    carrier=8e6;edges,iv,qv=square_fixture(carrier,8,8)
    offsets=[k*carrier/8 for k in range(-3,4)]
    components=iq_sidebands(edges,iv,qv,carrier,offsets)
    fundamental=iq_projection(edges,iv,qv,carrier)
    assert abs(components[3][1]-fundamental['desired'])<1e-14
    assert abs(components[3][2]-fundamental['image'])<1e-14
    fourier_errors=[]
    for offset,d,i in components:
        for frequency,actual in ((carrier+offset,d),(-carrier+offset,i)):
            total=0j
            for a,b,x,y in zip(edges,edges[1:],iv,qv):
                v,_=quad_vec(lambda t:(x+1j*y)*cmath.exp(-2j*math.pi*frequency*t),a,b,epsabs=1e-18)
                total+=v
            expected=total/(edges[-1]-edges[0])/(4/math.pi)
            fourier_errors.append(abs(actual-expected))
    assert max(fourier_errors)<1e-12
    sidebands=[c for c in components if c[0]]
    def plant():
        s=Session();tx=RfCascadeState(s);tx.set_reconstruction(Reconstruction())
        tx.rx_route='external_tone';tx.external_amplitude=.2+.1j;tx.external_frequency=.3e6
        c=SimpleNamespace(session=s,time=0.,tx=tx)
        connect(c,fundamental['desired'],fundamental['image'],sidebands)
        return tx
    rows=[]
    for duration in (30e-9,500e-9,2e-6):
        a=plant();b=plant()
        def integrand(t):
            z=(.2+.1j)*cmath.exp(2j*math.pi*.3e6*t)
            value=sum(cmath.exp(2j*math.pi*f*t)*(d*z+i*z.conjugate()) for f,d,i in components)
            return a.rx_pole*math.exp(-a.rx_pole*(duration-t))*value
        expected,_=quad_vec(integrand,0.,duration,epsabs=1e-12,epsrel=1e-11)
        a.advance(duration)
        for k in range(1,38):b.advance(duration*k/37)
        assert abs(a.received-expected)<1e-10
        assert abs(a.received-b.received)<1e-10
        rows.append(dict(duration_s=duration,quadrature_error=abs(a.received-expected),subdivision_error=abs(a.received-b.received)))
    # Slow modulation sidebands also propagate through the actual chip ADC/host.
    for mode in (0,1):
        baseline=TransceiverChip(trim_offsets_v=(0.,0.),watchdog_s=1e-3)
        impaired=TransceiverChip(trim_offsets_v=(0.,0.),watchdog_s=1e-3)
        connect(baseline,fundamental['desired'],fundamental['image'])
        connect(impaired,fundamental['desired'],fundamental['image'],sidebands)
        for c in (baseline,impaired):
            c.external_source([.2+.1j],0.,1.,offset_hz=.3e6)
            c.configure(mode,0.);c.advance(8e-6);c.capture(64,c.time+100e-9)
            c.advance(12e-6);c.host_decoder.finish()
            assert c.host_samples==c.adc_words and len(c.host_samples)==64
        assert baseline.host_samples!=impaired.host_samples
        rows.append(dict(mode=mode,captured=64,sidebands_change_codes=True))
    assert all(hashlib.sha256((p/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
    report=dict(status='passed',source_sha256=hashes,cases=rows,max_fourier_error=max(fourier_errors),physical_qualification=False,
        limitations=['Truncated periodic envelope; no carrier harmonics or switching-voltage mapping.',
                     'Slow-sideband fixture verifies integration, not 2.4 GHz RF feasibility.'])
    (p/'evidence/fast-lo-sidebands.json').write_text(json.dumps(report,indent=2)+'\n')
    print('LO sideband Fourier, filter, subdivision, and common-chip capture checks passed')
if __name__=='__main__':main()
