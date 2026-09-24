"""Bounded ordered raw-bit/event adapter; no line coding or protocol decisions.

Candidate internal interface only: host metadata encoding and clock-domain
crossing are not implemented here. Event codes are opaque external meanings.
"""
from collections import deque
import math


class BitEventStream:
    def __init__(self, capacity=16):
        if type(capacity) is not int or capacity<2:
            raise ValueError('At least two record slots required')
        self.capacity=capacity
        self.reset()

    def reset(self):
        self.records=deque();self.word=0;self.valid_bits=0
        self.time=0.;self.fault=False

    def _check(self,time):
        if self.fault:raise ValueError('Stream fault requires reset')
        if not math.isfinite(time) or time<self.time:
            raise ValueError('Monotonic observation time required')

    def _reserve(self,count):
        if len(self.records)+count>self.capacity:
            self.fault=True
            raise ValueError('Bit/event stream overflow')

    def bit(self,bit,time):
        self._check(time)
        if type(bit) is not int or bit not in (0,1):raise ValueError('Binary observation required')
        if self.valid_bits==9:self._reserve(1)
        self.word|=bit<<self.valid_bits;self.valid_bits+=1;self.time=time
        if self.valid_bits==10:
            self.records.append(('data',self.word,10,time))
            self.word=0;self.valid_bits=0

    def event(self,code,time):
        self._check(time)
        if type(code) is not int or not 0<=code<256:raise ValueError('Eight-bit event code required')
        # Reserve atomically: a boundary must never overtake its partial word.
        self._reserve(1+bool(self.valid_bits))
        if self.valid_bits:
            self.records.append(('data',self.word,self.valid_bits,time))
        self.records.append(('event',code,0,time))
        self.word=0;self.valid_bits=0;self.time=time

    def pop(self):
        if self.fault:raise ValueError('Stream fault requires reset')
        return self.records.popleft() if self.records else None
