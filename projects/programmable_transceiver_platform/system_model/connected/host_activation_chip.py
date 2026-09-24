"""Experimental full-chip host activation; default candidate is unchanged."""
import math
from coarse_retune_lifecycle import CoarseRetuningChip
from host_activation import HostActivation

class HostActivationChip(CoarseRetuningChip):
    TILE_COMMANDS=CoarseRetuningChip.TILE_COMMANDS+('host_train_start','host_train_status','host_train_abort')
    def __init__(self,**kwargs):
        self.host_activation=None
        super().__init__(**kwargs);self.host_activation=HostActivation()
    def _require_host(self):
        if not self.host_activation.ready(self.time,self.epoch):raise ValueError('Qualified current host activation required')
    def descriptor(self,*args,**kwargs):
        self._require_host();return super().descriptor(*args,**kwargs)
    def schedule(self,*args,**kwargs):
        self._require_host();return super().schedule(*args,**kwargs)
    def capture(self,*args,**kwargs):
        self._require_host();return super().capture(*args,**kwargs)
    def accept_wire(self,*args,**kwargs):
        self._require_host();return super().accept_wire(*args,**kwargs)
    def schedule_wire(self,*args,**kwargs):
        self._require_host();return super().schedule_wire(*args,**kwargs)
    def execute_management(self,operation,payload,time):
        if operation.startswith('host_train_'):
            if payload:raise ValueError('Reserved host-training payload')
            if operation=='host_train_start':
                if self.state!='active' or self.decoder is not None or self.tx.queue or self.wire_queue or self.adc_left or self.adc_pending or self.wire_remaining:
                    raise ValueError('Host training needs idle active clocks')
                if self.receiver.pos:raise ValueError('Host training needs a frame boundary')
                self.host_activation.start(self.session.mode,time,self.epoch,self.receiver.sequence,self.host_frame_words)
                return {}
            if operation=='host_train_status':
                a=self.host_activation
                return dict(value=('idle','training','ready','failed').index(a.state)|(a.words<<8))
            if operation=='host_train_abort':
                self.quiesce(time,'host training abort');return {}
        return super().execute_management(operation,payload,time)
    def feed(self,word,epoch,time):
        self.advance(time);a=self.host_activation
        if a.state=='training':
            try:a.feed(word,time,epoch)
            except ValueError as error:self.quiesce(time,str(error))
        else:
            if not a.ready(time,epoch):self.quiesce(time,'host activation missing or expired')
            else:a.last=time
        return super().feed(word,epoch,time)
    def advance(self,time):
        a=self.host_activation
        if a is not None and a.state=='training' and time>a.deadline:
            deadline=a.deadline
            super().advance(deadline)
            self.quiesce(deadline,'host training clock timeout')
        return super().advance(time)
    def quiesce(self,time,reason):
        if self.host_activation is not None:self.host_activation.invalidate(reason)
        return super().quiesce(time,reason)
    def reference_metrics(self):
        r=super().reference_metrics();a=self.host_activation
        r['host_activation']=dict(state=a.state,words=a.words,reason=a.reason,transitions=getattr(a,'transitions',0))
        return r
