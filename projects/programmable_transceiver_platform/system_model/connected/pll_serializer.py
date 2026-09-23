"""Serializer deadlines derived from bounded oscillator phase crossings."""
import math
from wired_serializer import Serializer


class PLLSerializer(Serializer):
    def __init__(self,channel,time,pll,bounded=False):
        super().__init__(channel,time)
        self.bounded=bool(bounded);self.pending_phase=False
        if pll.time>time:raise ValueError('Serializer cannot predate oscillator')
        pll.advance(time);self.pll=pll

    def start(self,word,time,ui):
        self.pll.advance(time)
        super().start(word,time,ui)
        self.origin_phase=self.pll.output_phase_cycles
        self.target_phase=self.origin_phase;self.pending_phase=False

    def step(self):
        if self.pending_phase:raise ValueError('Serializer phase target needs a longer supply forecast')
        self.pll.advance(self.deadline)
        word=super().step()
        if self.active:
            self.target_phase=self.origin_phase+self.bit+(.5 if self.stage=='sample' else 0.)
            self.retime()
        return word

    def retime(self):
        if not self.active:return
        if not self.bounded:
            self.deadline=self.pll.edge_time(self.target_phase);return
        history=self.pll.supply_trajectory
        if history is None:raise ValueError('Bounded serializer requires known supply history')
        crossing=self.pll.edge_time_before(self.target_phase,history.times[-1])
        self.pending_phase=crossing is None
        self.deadline=math.inf if crossing is None else crossing

    def abort(self,time):
        super().abort(time)
        self.pending_phase=False;self.target_phase=None
