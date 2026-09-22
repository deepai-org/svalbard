"""Independent simultaneous network/filter ODE versus connected loaded loopback."""
import cmath,hashlib,json,math
import numpy as np
from scipy.integrate import solve_ivp
from fast_loaded_output_check import plant
from fast_loaded_output import P
from tx_output_stage import output_envelope

def main():
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    a=plant();b=plant();oracle=plant()
    for c in (a,b,oracle):c.tx.rx_lo_hz=.8e6;c.tx.rx_lo_phase=-.1
    n=oracle.output_network;bank=oracle.tx.rx_bank
    poles=np.asarray(bank['poles']);weights=np.asarray(bank['weights'])
    drive=np.linalg.solve(n.C,np.array([1/50,0,0,0]))
    def rhs(t,y):
        v=y[:9]+1j*y[9:]
        source=output_envelope(oracle.tx.output_value(t),cmath.exp(1j*(2*math.pi*1.2e6*t+.3)),**oracle.tx_output_parameters)
        network=n.A@v[:4]+drive*source
        mixed=v[1]*cmath.exp(-1j*(2*math.pi*.8e6*t-.1))
        d=np.r_[network,poles*(mixed-v[4:])]
        return np.r_[d.real,d.imag]
    end=100e-9
    sol=solve_ivp(rhs,(0,end),np.zeros(18),method='Radau',rtol=1e-9,atol=1e-12)
    assert sol.success
    expected=np.sum(weights*(sol.y[4:9,-1]+1j*sol.y[13:18,-1]))
    a.tx.advance(end)
    for k in range(1,38):b.tx.advance(end*k/37)
    error=abs(a.tx.received-expected);split=abs(a.tx.received-b.tx.received)
    assert error<1e-9 and split<1e-10
    files=list((P/'system_model/connected').glob('*.py'))+list((P/'system_model/architecture_fast').glob('*.py'))+[P/'verification'/n for n in ('fast_loaded_output.py','fast_loaded_output_check.py','fast_loaded_loopback_check.py')]
    report=dict(status='passed',source_sha256={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
        rx_radau_error=error,rx_subdivision_error=split,physical_qualification=False,
        limitations=['Constant DAC input transient with differing fixed TX/RX LO offsets; managed traffic pending.',
                     'Assumed passive network, no driver current/supply limits.'])
    (P/'evidence/fast-loaded-loopback.json').write_text(json.dumps(report,indent=2)+'\n')
    print(error,split)
if __name__=='__main__':main()
