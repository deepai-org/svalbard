"""Frame identity, nonmutation and double-LO negative controls."""
import json,copy,pickle,math,cmath
import numpy as np
from chip_model import P
from rf_loaded_detector import LoadedDetector
from loaded_pad_observer import observe

def main():
    load=LoadedDetector();n=load.network;n.configure(True,False)
    phase=.8;slope=2*math.pi*7e6
    load.advance(20e-9,[(.2*cmath.exp(1j*phase),1j*slope)])
    saved=pickle.dumps(load)
    rows=[]
    for carrier in (2412000000,2437000000):
        actual=observe(n,n.time,carrier)
        # Independent physical analytic signal, then remove observation carrier.
        physical=n.voltage[1]*cmath.exp(1j*n.omega*n.time)
        expected=physical*cmath.exp(-2j*math.pi*carrier*n.time)
        assert abs(actual-expected)<1e-13
        assert pickle.dumps(load)==saved
        wrong=actual*cmath.exp(1j*(phase+slope*n.time))
        assert abs(wrong-actual)>1e-3
        rows.append(dict(carrier_hz=carrier,frame_error=abs(actual-expected),double_lo_error=abs(wrong-actual)))
    altered=copy.deepcopy(n);altered.voltage[1]*=.3
    assert abs(observe(altered,n.time,2412000000)-.3*observe(n,n.time,2412000000))<1e-15
    try:observe(n,n.time+1e-9,2412000000)
    except ValueError:pass
    else:raise AssertionError('Stale pad observation accepted')
    report=dict(status='passed',cases=rows,limitations=[
        'Observer assumes source already includes LO phase; caller must enforce this contract.',
        'No waveform quality claim; full-chip observer wrapper integration remains pending.'])
    (P/'evidence/connected-loaded-pad-observer.json').write_text(json.dumps(report,indent=2)+'\n');print(rows)

if __name__=='__main__':main()
