"""Serializer deadlines derived from bounded oscillator phase crossings."""
from wired_serializer import Serializer


class PLLSerializer(Serializer):
    def __init__(self,channel,time,pll):
        super().__init__(channel,time)
        if pll.time>time:raise ValueError('Serializer cannot predate oscillator')
        pll.advance(time);self.pll=pll

    def start(self,word,time,ui):
        self.pll.advance(time)
        super().start(word,time,ui)
        self.origin_phase=self.pll.output_phase_cycles
        self.target_phase=self.origin_phase

    def step(self):
        self.pll.advance(self.deadline)
        word=super().step()
        if self.active:
            self.target_phase=self.origin_phase+self.bit+(.5 if self.stage=='sample' else 0.)
            self.deadline=self.pll.edge_time(self.target_phase)
        return word

    def retime(self):
        if self.active:self.deadline=self.pll.edge_time(self.target_phase)
