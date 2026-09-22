"""Stateful RF TX consumer: queue reset and continuous analog filter state."""
from collections import deque
import math

class RfTxState:
    def __init__(self,session,capacity=128,bandwidth_hz=10e6):
        assert capacity>0 and bandwidth_hz>0
        self.session=session;self.capacity=capacity;self.pole=2*math.pi*bandwidth_hz
        self.queue=deque();self.time=0.;self.held=0j;self.filtered=0j;self.reconstruction=None
        self.admission_check=lambda:None
        self.sample_correction=lambda time,value:value
        self.dac_gain=lambda time:1.
        self.dac_transfer=lambda time,value:value
        self.accepted=0;self.consumed=0;self.discarded=0;self.rejected=0;self.underflows=0
    def advance(self,time):
        assert time>=self.time
        self.filtered=(self.reconstruction.advance(time,self.held) if self.reconstruction is not None else
            self.held+(self.filtered-self.held)*math.exp(-self.pole*(time-self.time)))
        self.time=time
    def set_reconstruction(self,reconstruction):
        if self.time or self.held or self.filtered or self.queue or self.reconstruction is not None:
            raise ValueError('TX topology selection requires a fresh unenergized state')
        if reconstruction.time or any(reconstruction.states):raise ValueError('Filter state must initially be unenergized')
        self.reconstruction=reconstruction
    def output_value(self,time):
        if time<self.time:raise ValueError('Output observation before TX state')
        if self.reconstruction is not None:return self.reconstruction.value(time,self.held)
        return self.held+(self.filtered-self.held)*math.exp(-self.pole*(time-self.time))
    def transmit_terms(self):
        if self.reconstruction is not None:return self.reconstruction.terms(self.held)
        return [(self.held,0j),(self.filtered-self.held,-self.pole)]
    def accept(self,value):
        self.admission_check()
        if not self.session.enabled('rf'):
            self.rejected+=1;return False
        if len(self.queue)>=self.capacity:raise OverflowError('RF DAC queue full')
        self.queue.append(complex(value));self.accepted+=1;return True
    def apply_sample(self,value,time):
        self.advance(time)
        gain=self.dac_gain(time)
        if not math.isfinite(gain) or gain<=0:raise ValueError('Invalid DAC gain')
        corrected=self.sample_correction(time,value)
        self.held=self.dac_transfer(time,corrected)*gain

    def clock(self,time):
        self.advance(time)
        if not self.session.enabled('rf'):self.held=0j
        elif self.queue:
            self.apply_sample(self.queue[0],time)
            self.queue.popleft();self.consumed+=1
        else:self.held=0j;self.underflows+=1
        return self.filtered
    def reset(self,time):
        self.advance(time)
        self.discarded+=len(self.queue);self.queue.clear();self.held=0j
        self.session.reset_engine('rf')
        # Stored analog charge decays naturally; reset does not erase it.
    def accounting(self):
        assert self.accepted==self.consumed+self.discarded+len(self.queue)
        return dict(accepted=self.accepted,consumed=self.consumed,discarded=self.discarded,
            pending=len(self.queue),rejected=self.rejected,underflows=self.underflows)


def controls():
    from session import Session
    s=Session();s.configure(0);s.host_ready=True;s.ready.update(rf=True,wire=True);s.arm()
    tx=RfTxState(s,4)
    for value in (1,.5,-.5):assert tx.accept(value)
    tx.clock(0);tx.reset(10e-9)
    expected=1-math.exp(-tx.pole*10e-9)
    assert abs(tx.filtered-expected)<1e-14 and tx.held==0
    assert s.enabled('wire') and not s.enabled('rf')
    assert not tx.accept(-1)  # Decoded traffic during rearm is explicitly rejected.
    tx.clock(20e-9)
    assert abs(tx.filtered-expected*math.exp(-tx.pole*10e-9))<1e-14
    assert tx.accounting()['discarded']==2
    # Fixture asserts upstream has drained before readiness; implementation of
    # that barrier is intentionally not claimed by this local consumer block.
    s.ready['rf']=True;assert tx.accept(.25);tx.clock(30e-9)
    assert tx.held==.25 and tx.accounting()['consumed']==2
    tx.clock(40e-9);assert tx.underflows==1 and tx.held==0
    return tx.accounting()

if __name__=='__main__':
    import hashlib,json
    from pathlib import Path
    p=Path(__file__).resolve().parents[2]
    report=dict(controls=controls(),complete_architecture=False,
        source_hashes={str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in (Path(__file__),Path(__file__).with_name('session.py'))},
        limitations=['Consumer block only; not yet connected to framed transport/reset propagation.',
          'No physical filter-reset switch: retained analog state follows hypothetical one-pole response.',
          'Upstream drain/rearm barrier is assumed; late old-epoch words after rearm remain unresolved.'])
    (p/'evidence/rf-tx-reset-state.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
