"""Standalone RC load-discrimination experiment; no protocol threshold claim."""
import itertools,json,hashlib
from pathlib import Path
import numpy as np
from scipy.linalg import expm
from scipy.integrate import solve_ivp,quad


def matrices(cp,cc,cr,rs,rt):
    C=np.array([[cp+cc,-cc],[-cc,cc+cr]])
    G=np.diag([1/rs,1/rt])
    A=-np.linalg.solve(C,G)
    return C,G,A


def response(params,time,u=.2):
    C,G,A=matrices(**params)
    equilibrium=np.array([u,0.])
    return equilibrium-expm(A*time)@equilibrium


def classify(normalized):
    # Frozen candidate regions, deliberately leaving an ambiguous interval.
    if all(x<.65 for x in normalized):return 'present'
    if all(x>.85 for x in normalized):return 'absent'
    return 'indeterminate'


def main():
    rows=[];times=(100e-9,1e-6)
    for cp,cc,cr,rs,rt in itertools.product((1e-12,10e-12),(10e-9,100e-9),(1e-12,10e-12),(100.,1000.),(40.,100.,1e5,1e8)):
        p=dict(cp=cp,cc=cc,cr=cr,rs=rs,rt=rt)
        values=[float(response(p,t)[0]/.2) for t in times]
        result=classify(values);expected='present' if rt<=100 else 'absent'
        assert result in (expected,'indeterminate'),(p,values,result)
        rows.append(dict(parameters=p,normalized_samples=values,result=result,expected=expected))
    # Independent time-domain integration and energy accounting at an interior point.
    p=dict(cp=5e-12,cc=47e-9,cr=3e-12,rs=470.,rt=75.)
    C,G,A=matrices(**p);u=.2;T=1e-6
    b=np.linalg.solve(C,np.array([u/p['rs'],0.]))
    sol=solve_ivp(lambda t,x:A@x+b,(0,T),[0.,0.],method='Radau',rtol=1e-10,atol=1e-12)
    expected=response(p,T);error=float(max(abs(sol.y[:,-1]-expected)));assert error<1e-8
    def powers(t):
        v,w=response(p,t);current=(u-v)/p['rs']
        return u*current,current**2*p['rs']+w*w/p['rt']
    source=quad(lambda t:powers(t)[0],0,T,epsabs=1e-19)[0]
    loss=quad(lambda t:powers(t)[1],0,T,epsabs=1e-19)[0]
    stored=float(expected@C@expected/2);residual=source-loss-stored
    assert abs(residual)<1e-17
    # Small coupling capacitors make a terminated receiver resemble an open at
    # late times: preserve this as a failure of the proposed operating envelope.
    outside=dict(p,cc=100e-12)
    v=[float(response(outside,t)[0]/u) for t in times]
    assert classify(v)!='present'
    report=dict(status='passed',standalone=True,connected=False,physical_qualification=False,
        cases=rows,observation_times_s=times,stimulus_v=u,regions=dict(present_below=.65,absent_above=.85),
        solver_error_v=error,energy_residual_j=residual,
        outside_envelope=dict(parameters=outside,normalized_samples=v,result=classify(v)),
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        limitations=['Assumed load ranges, zero initial capacitor voltages and ideal noiseless sensors.',
        'Corner checks are not continuous-envelope or package qualification; thresholds are not PCIe specifications.',
        'No two-leg controller, finite-release sequence, current/supply coupling or connected lifecycle yet.'])
    (Path(__file__).resolve().parents[2]/'evidence/receiver-detect-load-screen.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed',len(rows),'load corners; solver error',error,'energy residual',residual,'outside',classify(v))

if __name__=='__main__':main()
