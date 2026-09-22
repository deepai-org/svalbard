"""Response, independent state-space propagation, memory and image-tone controls."""
import copy,json,math
import numpy as np
from scipy import signal,linalg
from chip_model import P
from tx_reconstruction import Reconstruction

def main():
 rows=[]
 for kind in ('butterworth','chebyshev','elliptic'):
    f=Reconstruction(kind);freq=np.r_[np.linspace(0,8e6,20001),np.geomspace(12e6,2e9,40000)]
    loss=-20*np.log10(np.maximum(abs(f.response(freq)),1e-300))
    assert max(loss[:20001])<=1.0001 and min(loss[20001:])>=29.999
    # Independent real companion state-space matrix exponential under complex input.
    a,b,c,d=signal.tf2ss(f.b,f.a);n=len(a)
    aug=np.zeros((n+1,n+1));aug[:n,:n]=a;aug[:n,n:]=b
    z=np.zeros(n+1,complex);worst=0.
    for step,u in enumerate((.3+.2j,-.15+.1j,0j,.1-.2j)):
        interval=(step+1)*13e-9;z[-1]=u
        z=linalg.expm(aug*(interval*f.scale))@z
        expected=complex((c@z[:n]+d*u).item())
        trial=copy.deepcopy(f)
        actual=f.advance(f.time+interval,u)
        for part in range(1,38):trial.advance(f.time-interval+part*interval/37,u)
        worst=max(worst,abs(actual-expected))
        assert abs(actual-expected)<2e-9 and abs(actual-complex(np.sum(trial.residues*trial.states)))<1e-11
    at_switch=f.value(f.time,0j);assert abs(at_switch-f.value(f.time,.7j))<1e-14
    old=at_switch;f.advance(f.time+1e-9,0j);assert abs(f.value(f.time,0j))>0 and abs(f.value(f.time,0j)-old)<.1
    f.advance(f.time+20e-6,0j);assert abs(f.value(f.time,0j))<1e-12
    rows.append(dict(**f.metrics(),max_pass_loss_db=float(max(loss[:20001])),min_stop_loss_db=float(min(loss[20001:])),
        matrix_exponential_max_error=worst,worst_first_image_edge_db=float(20*np.log10(abs(f.response([12.1875e6])[0])))))
 report=dict(status='passed',cases=rows,complete_architecture=False,physical_qualification=False,
    scope='Provisional 8MHz passband / 12MHz stopband, <=1dB filter loss and >=30dB rejection; not a protocol mask.',
    limitations=['Filter gain/phase and states only; no op-amp noise, slew, mismatch, component tuning, loading, power or area qualification.',
      'Buffer pole is an assumed 80MHz stage and is included in order and loss.',
      'DAC sinc droop, burst spectrum and downstream LO/mixer effects require connected tests.'])
 (P/'evidence/connected-tx-reconstruction.json').write_text(json.dumps(report,indent=2)+'\n')
 for r in rows:print(r['kind'],r['total_order'],r['pole_pair_q'],r['matrix_exponential_max_error'])
if __name__=='__main__':main()
