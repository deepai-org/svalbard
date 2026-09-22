"""Immutable finite spectral frequency-noise realization in output-Hz units.

Random phases are drawn once. Queries and solver subdivisions consume no random
numbers. Lines approximate a declared band; this is not an infinite-band white
noise process or a calibrated device phase-noise spectrum.
"""
from dataclasses import dataclass
import math
import random


@dataclass(frozen=True)
class FrequencyNoise:
    tones: tuple

    def __post_init__(self):
        rows=tuple(tuple(float(v) for v in row) for row in self.tones)
        if any(len(row)!=3 or not all(math.isfinite(v) for v in row) or row[0]<=0 for row in rows):
            raise ValueError('Noise lines require positive frequency and finite amplitude/phase')
        if not math.isfinite(sum(abs(a) for _,a,_ in rows)):
            raise ValueError('Unbounded spectral amplitude')
        object.__setattr__(self,'tones',rows)

    @property
    def bound_hz(self):return sum(abs(a) for _,a,_ in self.tones)

    @property
    def integration_step_s(self):
        return 1/(32*max(f for f,_,_ in self.tones)) if self.tones else math.inf

    def frequency(self,time):
        return sum(a*math.cos(2*math.pi*f*time+p) for f,a,p in self.tones)

    def phase_integral(self,start,end):
        """Exact accumulated cycles for this immutable frequency realization."""
        if not all(math.isfinite(t) for t in (start,end)) or end<start:
            raise ValueError('Invalid noise integration interval')
        dt=end-start;mid=start+dt/2
        return sum(a/(math.pi*f)*math.sin(math.pi*f*dt)*math.cos(2*math.pi*f*mid+p)
                   for f,a,p in self.tones)

    @classmethod
    def seeded(cls,rms_hz,spacing_hz=250e3,lines=8,seed=830):
        if not math.isfinite(rms_hz) or rms_hz<0 or not math.isfinite(spacing_hz) or spacing_hz<=0 or not isinstance(lines,int) or lines<1:
            raise ValueError('Invalid finite noise band')
        if rms_hz==0:return cls(())
        rng=random.Random(seed);amplitude=rms_hz*math.sqrt(2/lines)
        return cls(tuple((spacing_hz*(i+1),amplitude,rng.uniform(-math.pi,math.pi)) for i in range(lines)))
