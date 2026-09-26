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


class SampledActivityBoundary:
    """Generic sampled activity-to-record adapter, not packet/EOP recognition.

    Sampling clock and activity comparator are external. A qualified inactive
    interval ends a burst. A shorter dropout followed by activity faults rather
    than silently merging samples across an uncertain interval.
    """
    def __init__(self,stream,quiet_samples=2,event_code=7):
        if type(quiet_samples) is not int or quiet_samples<1:
            raise ValueError('Positive integer inactivity qualification')
        if type(event_code) is not int or not 0<=event_code<256:
            raise ValueError('Eight-bit event code')
        self.stream=stream;self.quiet_samples=quiet_samples;self.event_code=event_code
        self.in_burst=False;self.quiet=0;self.last_time=None;self.fault=False

    def observe(self,active,bit,time):
        if self.fault or self.stream.fault:raise ValueError('Activity adapter fault')
        if type(active) is not bool or type(bit) is not int or bit not in (0,1):
            raise ValueError('Boolean activity and binary sample required')
        if not math.isfinite(time) or (self.last_time is not None and time<=self.last_time):
            raise ValueError('Strictly increasing sample times required')
        self.stream._check(time)
        if active and self.in_burst and self.quiet:
            self.fault=self.stream.fault=True
            raise ValueError('Unqualified activity dropout')
        if active:
            self.stream.bit(bit,time);self.in_burst=True;self.quiet=0
        elif self.in_burst:
            self.quiet+=1
            if self.quiet==self.quiet_samples:
                self.stream.event(self.event_code,time)
                self.in_burst=False;self.quiet=0
        self.last_time=time


class RawBurstPlayback:
    """Candidate raw-record TX consumer; event marks end, not a protocol opcode.

    tick() returns one physical line-level bit or None for released output.
    Record arrival and serializer clock/CDC are supplied by the caller. Storage
    is bounded; an incomplete active burst underruns instead of repeating data.
    """
    def __init__(self,capacity_bits=2048,boundary_code=7,max_boundaries=16):
        if type(capacity_bits) is not int or capacity_bits<1 or type(max_boundaries) is not int or max_boundaries<1:
            raise ValueError('Positive playback capacities')
        if type(boundary_code) is not int or not 0<=boundary_code<256:
            raise ValueError('Eight-bit boundary code')
        self.capacity_bits=capacity_bits;self.boundary_code=boundary_code
        self.max_boundaries=max_boundaries;self.queue=deque()
        self.bits=0;self.boundaries=0;self.active=False;self.fault=False
        self.emitted=0;self.completed=0

    def _fail(self,reason):
        self.fault=True;self.active=False
        raise ValueError(reason)

    def enqueue(self,records):
        if self.fault:raise ValueError('Playback fault')
        pending=[];bits=0;boundaries=0
        for kind,value,count in records:
            if kind=='data' and type(count) is int and 1<=count<=10 and type(value) is int and 0<=value<1<<count:
                pending.extend((value>>n)&1 for n in range(count));bits+=count
            elif kind=='event' and count==0 and value==self.boundary_code:
                pending.append(None);boundaries+=1
            else:self._fail('Invalid playback record')
        if self.bits+bits>self.capacity_bits or self.boundaries+boundaries>self.max_boundaries:
            self._fail('Playback overflow')
        self.queue.extend(pending);self.bits+=bits;self.boundaries+=boundaries

    def tick(self):
        if self.fault:return None  # Fail released; no stale queued bits escape.
        if not self.queue:
            if self.active:self._fail('Playback underrun')
            return None
        value=self.queue.popleft()
        if value is None:
            self.boundaries-=1;self.completed+=1;self.active=False
            return None
        self.bits-=1;self.emitted+=1;self.active=True
        return value
