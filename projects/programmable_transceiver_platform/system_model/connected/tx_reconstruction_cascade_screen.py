"""Continuous reconstruction connected through RF loopback and receiver filter."""
import copy,json,numpy as np
from scipy import signal,linalg
from chip_model import P
from session import Session
from rf_cascade_state import RfCascadeState,controls as original_controls
from tx_reconstruction import Reconstruction

def main():
 original_controls()
 session=Session();session.configure(0);session.host_ready=True;session.ready.update(rf=True,wire=True);session.arm()
 tx=RfCascadeState(session);f=Reconstruction();tx.set_reconstruction(f)
 # Independent normalized transfer-function cascade Htx * Hrx.
 rx=tx.rx_pole/f.scale;b=f.b*rx;a=np.polymul(f.a,[1,rx])
 aa,bb,cc,dd=signal.tf2ss(b,a);n=len(aa);aug=np.zeros((n+1,n+1));aug[:n,:n]=aa;aug[:n,n:]=bb
 state=np.zeros(n+1,complex);worst=0.
 for index,u in enumerate((.15+.1j,-.12+.03j,.08-.07j,0j)):
    tx.apply_sample(u,tx.time);state[-1]=u;dt=(index+1)*27e-9
    split=copy.deepcopy(tx);end=tx.time+dt
    state=linalg.expm(aug*(dt*f.scale))@state;expected=complex((cc@state[:n]+dd*u).item())
    tx.advance(end)
    for i in range(1,30):split.advance(end-dt+i*dt/29)
    worst=max(worst,abs(tx.received-expected))
    assert abs(tx.received-expected)<1e-10 and abs(tx.received-split.received)<1e-11
    assert abs(tx.filtered-split.filtered)<1e-11
 old=tx.filtered;states=f.states.copy();tx.reset(tx.time)
 assert np.array_equal(states,f.states) and tx.filtered==old and tx.held==0
 before=f.states.copy();tx.output_value(tx.time+7e-9);assert np.array_equal(before,f.states)
 tx.advance(tx.time+20e-6);assert abs(tx.filtered)<1e-12 and abs(tx.received)<1e-12
 report=dict(status='passed',matrix_cascade_max_error=worst,
 controls=['original one-pole regression','independent TX/RX cascade transfer','29-way subdivision','reset retains modal state','nonmutating observation','ring-down'],
 limitations=['Ideal linear reconstruction; amplifier/switch/reference loading and nonlinear output stage remain unqualified.'])
 (P/'evidence/connected-tx-reconstruction-cascade.json').write_text(json.dumps(report,indent=2)+'\n')
 print('Passed reconstruction/cascade integration, original controls and retained-state reset')
if __name__=='__main__':main()
