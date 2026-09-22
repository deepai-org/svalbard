"""Independent cascade ODE, step settling and retained readout state."""
import json,copy
import numpy as np
from scipy.integrate import solve_ivp
from chip_model import P
from detector_readout_settling import SettlingDetector

def main():
    rows=[]
    for tau in (5e-9,20e-9,500e-9):
        c=SettlingDetector(readout_tau_s=tau);c.value=.005;c.readout_value=.002
        terms=[(.15+.1j,0j),(.03-.02j,-1e7+2e7j)]
        end=500e-9
        def ode(t,y):
            power=abs(sum(v*np.exp(p*t) for v,p in terms))**2
            return [c.pole*(power-y[0]),c.readout_pole*(y[0]-y[1])]
        solution=solve_ivp(ode,(0,end),[c.value,c.readout_value],rtol=1e-10,atol=1e-13,method='DOP853')
        assert solution.success
        split=copy.deepcopy(c);c.advance(end,terms)
        split.advance(end/2,terms);split.advance(end,[(v*np.exp(p*end/2),p) for v,p in terms])
        err=float(max(abs(np.array([c.value,c.readout_value])-solution.y[:,-1])))
        assert err<1e-10 and abs(c.readout_value-split.readout_value)<1e-12
        value=c.readout_value;c.abort();assert c.readout_value==value
        rows.append(dict(readout_tau_s=tau,ode_error=err,detector=c.value,readout=c.readout_value))
    r=dict(status='passed',cases=rows,limitations=[
        'One-way buffered cascade; finite mux reverse loading and ADC kickback not represented.',
        'Readout state not yet selected by shared ADC sampling callback.',
        'Explicitly rejects coincident poles; values are exploratory, not PDK-derived.'])
    (P/'evidence/connected-detector-readout-settling.json').write_text(json.dumps(r,indent=2)+'\n');print(rows)

if __name__=='__main__':main()
