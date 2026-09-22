"""Independent quadrature oracle for nonlinear output -> loopback RX filter."""
import cmath,hashlib,json,math
from pathlib import Path
from scipy.integrate import quad_vec
from output_loopback import receive_terms,architecture
from rf_cascade_state import RfCascadeState
from tx_reconstruction import Reconstruction
from tx_output_stage import output_envelope
from session import Session
from types import MethodType
PARAMETERS=dict(gain_imbalance_db=.25,phase_error_deg=2.,lo_feedthrough=.0025,cubic=.06)

def plant():
    s=RfCascadeState(Session());s.set_reconstruction(Reconstruction())
    s.tx_lo_hz=1.2e6;s.rx_lo_hz=.8e6;s.tx_lo_phase=.2;s.rx_lo_phase=-.1
    s.apply_sample(.2+.1j,0.)
    s.receive_terms=MethodType(lambda state:receive_terms(state,PARAMETERS),s)
    return s

def main():
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    p=architecture.P
    files=list(architecture.D.glob('*.py'))+list(Path(__file__).parent.glob('*.py'))+[p/'verification/stream_codec.py']
    hashes={str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    rows=[]
    for duration in (30e-9,500e-9,2e-6):
        a=plant();b=plant();oracle=plant()
        def integrand(t):
            phase=2*math.pi*(oracle.tx_lo_hz-oracle.rx_lo_hz)*t+oracle.tx_lo_phase-oracle.rx_lo_phase
            value=complex(output_envelope(oracle.output_value(t),cmath.exp(1j*phase),**PARAMETERS))
            return oracle.rx_pole*math.exp(-oracle.rx_pole*(duration-t))*value
        expected,error=quad_vec(integrand,0.,duration,epsabs=1e-12,epsrel=1e-11)
        a.advance(duration)
        for i in range(1,38):b.advance(duration*i/37)
        assert abs(a.received-expected)<1e-10
        assert abs(a.received-b.received)<1e-10
        rows.append(dict(duration_s=duration,quadrature_error=abs(a.received-expected),
                         subdivision_error=abs(a.received-b.received),oracle_error_estimate=float(error)))
    assert all(hashlib.sha256((p/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
    (p/'evidence/fast-output-loopback.json').write_text(json.dumps(dict(status='passed',source_sha256=hashes,cases=rows,
        physical_qualification=False,limitations=['Constant DAC input with assumed memoryless output distortion; full-chip traffic pending.',
        'No output loading, harmonics outside envelope or physical parameter qualification.']),indent=2)+'\n')
    print(rows)
if __name__=='__main__':main()
