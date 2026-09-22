"""Finite output adapter: initial transient, phase and switch-state continuity."""
import hashlib,json
import numpy as np
from scipy.integrate import solve_ivp
from fast_loaded_output import LoadedOutputChip,P
from tx_output_stage import output_envelope

def plant():
    c=LoadedOutputChip();c.output_network.configure(True,False)
    c.tx.tx_lo_hz=1.2e6;c.tx.tx_lo_phase=.3
    c.tx.apply_sample(.2+.1j,0.)
    return c

def main():
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    a=plant();b=plant();oracle=plant();n=oracle.output_network
    # Stiff Radau integration in real coordinates, independent of modal solver.
    import cmath,math
    drive=np.linalg.solve(n.C,np.array([1/50,0,0,0]))
    def rhs(t,y):
        v=y[:4]+1j*y[4:]
        source=output_envelope(oracle.tx.output_value(t),cmath.exp(1j*(2*math.pi*1.2e6*t+.3)),**oracle.tx_output_parameters)
        d=n.A@v+drive*source
        return np.r_[d.real,d.imag]
    end=30e-9
    sol=solve_ivp(rhs,(0,end),np.zeros(8),method='Radau',rtol=1e-9,atol=1e-12)
    assert sol.success
    a.tx.advance(end)
    for i in range(1,38):b.tx.advance(end*i/37)
    expected=sol.y[:4,-1]+1j*sol.y[4:,-1]
    error=float(np.max(abs(a.output_network.voltage-expected)))
    split=float(np.max(abs(a.output_network.voltage-b.output_network.voltage)))
    assert error<1e-9 and split<1e-10
    before=a.output_network.voltage.copy();a.output_network.configure(False,True)
    assert np.array_equal(before,a.output_network.voltage)
    a.tx.advance(end+10e-9)
    assert abs(a.output_network.voltage[1])<abs(before[1])
    files=list((P/'system_model/connected').glob('*.py'))+list((P/'system_model/architecture_fast').glob('*.py'))+[P/'verification/fast_loaded_output.py',P/'verification/fast_loaded_output_check.py']
    report=dict(status='passed',source_sha256={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
        radau_error=error,subdivision_error=split,switch_voltage_continuous=True,
        physical_qualification=False,limitations=['Direct analog transient only; full-chip event/capture regression pending.',
        'Calibration detector and RX loopback are not yet connected to loaded network.',
        'Assumed passive RC pad network; no nonlinear driver or supply current model.'])
    (P/'evidence/fast-loaded-output.json').write_text(json.dumps(report,indent=2)+'\n')
    print(error,split)
if __name__=='__main__':main()
