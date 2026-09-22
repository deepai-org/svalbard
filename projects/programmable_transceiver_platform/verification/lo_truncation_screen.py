"""Envelope truncation versus exact periodic switched-mixer/filter response.

The oracle integrates real RF times piecewise constant complex switching drive,
including carrier harmonics, with a first-order receiver filter. No time step
approximation and no Fourier coefficients are used in the oracle.
"""
import cmath,hashlib,json,math,sys
from pathlib import Path
P=Path(__file__).resolve().parents[1]
F=P/'system_model/architecture_fast'
sys.path.insert(0,str(F))
from lo_drive import square_fixture,iq_sidebands

def screen(carrier,period,cutoff):
    edges,iv,qv=square_fixture(carrier,period,period)
    pole=2*math.pi*cutoff;omega=2*math.pi*carrier
    z=.2+.1j;normalization=4/math.pi
    def step(y,a,b,i,q):
        dt=b-a;decay=math.exp(-pole*dt);drive=(i+1j*q)/normalization
        result=y*decay
        for amplitude,rate in ((z,-1j*omega),(z.conjugate(),1j*omega)):
            result+=drive*amplitude*pole/(pole+rate)*(cmath.exp(rate*b)-decay*cmath.exp(rate*a))
        return result
    y=0j
    for a,b,i,q in zip(edges,edges[1:],iv,qv):y=step(y,a,b,i,q)
    # Periodic steady state rather than startup transient.
    initial=y/(-math.expm1(-pole*edges[-1]));y=initial
    times=[];truth=[]
    for a,b,i,q in zip(edges,edges[1:],iv,qv):
        for j in range(1,9):
            t=a+(b-a)*j/8
            times.append(t);truth.append(step(y,a,t,i,q))
        y=step(y,a,b,i,q)
    assert abs(y-initial)<1e-12
    scale=math.sqrt(sum(abs(v)**2 for v in truth)/len(truth))
    rows=[]
    for count in (0,1,3,7,15):
        if count>=period:continue
        terms=iq_sidebands(edges,iv,qv,carrier,[k*carrier/period for k in range(-count,count+1)])
        estimated=[sum((d*z+i*z.conjugate())*pole/(pole+2j*math.pi*f)*cmath.exp(2j*math.pi*f*t)
                       for f,d,i in terms) for t in times]
        error=math.sqrt(sum(abs(a-b)**2 for a,b in zip(estimated,truth))/len(truth))/scale
        rows.append(dict(sidebands_each_side=count,relative_rms_error=error))
    # A retained spectrum must improve on fundamental-only for this fixture.
    assert rows[-1]['relative_rms_error']<rows[0]['relative_rms_error']
    return dict(carrier_hz=carrier,missing_i_period=period,cutoff_hz=cutoff,
                periodic_closure_error=abs(y-initial),truncations=rows)

def main():
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    files=[Path(__file__),F/'lo_drive.py']
    hashes={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    cases=[screen(carrier,period,10e6) for carrier in (80e6,2.4e9) for period in (8,16)]
    for case in cases:
        residual=case['truncations'][-1]['relative_rms_error']
        if case['carrier_hz']==2.4e9:assert residual<.003
        else:assert residual>.05  # Negative control: envelope approximation is insufficient.
    result=dict(status='passed',source_sha256=hashes,cases=cases,physical_qualification=False,
        limitations=['Constant complex RF envelope, periodic missing I cycle, first-order 10 MHz filter.',
                     'Retained sidebands omit carrier harmonics; residual error is measured, not assumed zero.',
                     'Switching effectiveness is ideal normalized drive, not a transistor gate-voltage model.'])
    (P/'evidence/lo-truncation-screen.json').write_text(json.dumps(result,indent=2)+'\n')
    for c in cases:print(c)
if __name__=='__main__':main()
