"""Independent ODE and quadrature checks of loaded detector connection."""
import json
import numpy as np
from scipy.integrate import solve_ivp,quad
from chip_model import P
from rf_loaded_detector import LoadedDetector,voltage_terms

def main():
    rows=[]
    source=[(.2+.1j,0j),(-.1+.04j,-2e8+3e7j)]
    for output,dummy in ((False,True),(True,False),(False,False),(True,True)):
        c=LoadedDetector();n=c.network;n.voltage=n.steady(.1)
        before=n.voltage.copy();n.configure(output,dummy)
        assert np.array_equal(n.voltage,before)
        initial=.007;c.detector.value=initial
        drive=np.linalg.solve(n.C,np.array([1/50,0,0,0]))
        duration=300e-12
        def ode(t,v):return n.A@v+drive*sum(a*np.exp(p*t) for a,p in source)
        independent=solve_ivp(ode,(0,duration),before,method='DOP853',rtol=1e-10,atol=1e-13,dense_output=True)
        assert independent.success
        pole=c.detector.pole
        expected=initial*np.exp(-pole*duration)+quad(lambda t:pole*np.exp(-pole*(duration-t))*abs(independent.sol(t)[2])**2,0,duration,epsabs=1e-14)[0]
        actual=c.advance(duration,source)
        err=float(max(abs(actual-independent.y[:,-1])))
        assert err<1e-10 and abs(c.detector.value-expected)<1e-12
        # State and source phase must agree after subdividing the same interval.
        split=LoadedDetector();split.network.voltage=before.copy();split.network.configure(output,dummy);split.detector.value=initial
        split.advance(duration/2,source)
        split.advance(duration,[(a*np.exp(p*duration/2),p) for a,p in source])
        assert max(abs(split.network.voltage-actual))<1e-12
        assert abs(split.detector.value-c.detector.value)<1e-12
        c.detector.request();capture=c.detector.pending[2]
        # Switching after sampling must not rewrite the captured ADC code.
        n.configure(not output,not dummy)
        c.advance(c.detector.pending[0],[(.2,0j)])
        reply=c.detector.read();assert reply['code']==capture
        rows.append(dict(output_on=output,dummy_on=dummy,ode_voltage_error=err,
            detector_quadrature_error=abs(expected-split.detector.value),captured_code=capture,
            subsequent_detector_value=c.detector.value))
    r=dict(status='passed',cases=rows,limitations=[
        'Local electrical-network/detector composition; not yet connected to managed full-chip calibration.',
        'Source is prescribed RMS voltage, not a nonlinear active driver with supply-current feedback.',
        'Fixed carrier, linear RC and nonresonant exponential forcing; ill-conditioned modes rejected.',
        'No device/package qualification or calibration-accuracy certificate.'])
    (P/'evidence/connected-rf-loaded-detector.json').write_text(json.dumps(r,indent=2)+'\n');print(rows)

if __name__=='__main__':main()
