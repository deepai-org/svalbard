"""Candidate coherent sideband snapshot; register allocation/RTL not implemented."""
class ResetStatus:
    def __init__(self):
        self.epoch=0;self.accepted_words=0;self.last_boundary=0
        self.discarded_bits=0;self.overflow=False;self.latched=None
    def accepted(self):
        if self.accepted_words==(1<<64)-1:self.overflow=True
        else:self.accepted_words+=1
    def reset_event(self,partial_bits):
        assert 0<=partial_bits<10
        if self.epoch==(1<<32)-1:self.overflow=True
        else:self.epoch+=1
        self.last_boundary=self.accepted_words;self.discarded_bits=partial_bits
    def snapshot(self):
        self.latched=dict(epoch=self.epoch,accepted_word_boundary=self.last_boundary,
                          discarded_partial_bits=self.discarded_bits,overflow=self.overflow)
        return dict(self.latched)
    def read_snapshot(self):
        if self.latched is None:raise ValueError('Snapshot required')
        return dict(self.latched)

def controls():
    s=ResetStatus();s.accepted();s.reset_event(7);old=s.snapshot()
    s.accepted();s.reset_event(2)
    assert s.read_snapshot()==old
    assert s.snapshot()['accepted_word_boundary']==2
    s.epoch=(1<<32)-1;s.reset_event(0)
    assert s.overflow and s.epoch==(1<<32)-1


class HostResetObserver:
    """Starts at a jointly established stream/count origin; ambiguity requires re-arm."""
    def __init__(self):
        self.epoch=0;self.boundary=0;self.last=None;self.fault=False
    def observe(self,snapshot):
        if self.fault:raise ValueError('Re-arm required after ambiguous reset history')
        epoch=snapshot['epoch'];boundary=snapshot['accepted_word_boundary']
        if (snapshot['overflow'] or epoch not in (self.epoch,self.epoch+1)
                or boundary<self.boundary
                or (epoch==self.epoch and self.last is not None and snapshot!=self.last)):
            self.fault=True
            raise ValueError('Ambiguous reset history')
        changed=epoch!=self.epoch
        self.epoch=epoch;self.boundary=boundary;self.last=dict(snapshot)
        return dict(new_reset=changed,accepted_word_boundary=boundary,
                    discarded_partial_bits=snapshot['discarded_partial_bits'])


def observer_controls():
    device=ResetStatus();host=HostResetObserver()
    assert not host.observe(device.snapshot())['new_reset']
    device.accepted();device.reset_event(3)
    assert host.observe(device.snapshot())['new_reset']
    assert not host.observe(device.read_snapshot())['new_reset']
    device.reset_event(1);device.reset_event(2)
    try:host.observe(device.snapshot())
    except ValueError:assert host.fault
    else:raise AssertionError('Skipped reset epochs accepted')
    for update in ({'epoch':0,'accepted_word_boundary':0,'discarded_partial_bits':0,'overflow':False},
                   {'epoch':1,'accepted_word_boundary':1,'discarded_partial_bits':3,'overflow':True}):
        h=HostResetObserver();h.observe(dict(epoch=1,accepted_word_boundary=1,discarded_partial_bits=3,overflow=False))
        try:h.observe(update)
        except ValueError:assert h.fault
        else:raise AssertionError('Rollback or overflow accepted')
