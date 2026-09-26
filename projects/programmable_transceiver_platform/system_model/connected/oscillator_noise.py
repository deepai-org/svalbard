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


@dataclass(frozen=True)
class PhaseNoise:
    """Finite stationary phase lines in radians; reusable across time queries.

    Distinct-line variance is sum(peak**2/2); equal-frequency lines combine
    coherently. This differs from measured variance of a short burst. Close-in
    noise is not demeaned or renormalized
    to force a desired RMS within a packet. No measured GF180 spectrum implied.
    """
    tones: tuple

    def __post_init__(self):
        rows=tuple(tuple(float(x) for x in row) for row in self.tones)
        if any(len(r)!=3 or not all(math.isfinite(x) for x in r) or r[0]<=0 for r in rows):
            raise ValueError('Phase lines need positive frequency and finite amplitude/phase')
        if not math.isfinite(sum(abs(a) for _,a,_ in rows)):
            raise ValueError('Unbounded phase spectrum')
        object.__setattr__(self,'tones',rows)

    @property
    def variance_rad2(self):
        lines={}
        for f,a,p in self.tones:
            lines[f]=lines.get(f,0j)+a*complex(math.cos(p),math.sin(p))
        return sum(abs(a)**2/2 for a in lines.values())

    @property
    def maximum_offset_hz(self):return max((f for f,_,_ in self.tones),default=0.)

    def phase(self,times):
        import numpy as np
        times=np.asarray(times,float)
        if not np.all(np.isfinite(times)):raise ValueError('Finite phase query times required')
        value=np.zeros_like(times)
        for f,a,p in self.tones:value+=a*np.cos(2*math.pi*f*times+p)
        return value

    def plus(self,other):return PhaseNoise(self.tones+other.tones)

    @classmethod
    def from_ssb(cls,*,colored_at_100khz_dbc_hz, floor_dbc_hz,
                 offset_band_hz=(1e3,8e6),bins=96,seed=831,
                 loop_pole_hz=0.,injection='direct'):
        """1/f² + floor SSB spectrum through an assigned first-order transfer.

        S_phi=2*10**(L/10). Integrate each input bin analytically, then apply
        the complex transfer at its geometric center. 'vco' uses s/(s+B),
        'reference' uses B/(s+B); reference PSD is already LO-output-referred.
        Finite lines and a first-order pole do not establish PLL stability,
        spurs or a continuous broadband noise process.
        """
        import numpy as np
        lo,hi=offset_band_hz
        if (not all(math.isfinite(v) for v in (lo,hi,colored_at_100khz_dbc_hz,floor_dbc_hz,loop_pole_hz))
                or not 0<lo<hi or type(bins) is not int or bins<2
                or injection not in ('direct','vco','reference')
                or loop_pole_hz<0 or (injection!='direct' and loop_pole_hz<=0)):
            raise ValueError('Finite ordered spectral band and valid loop transfer required')
        edges=np.geomspace(lo,hi,bins+1);rng=random.Random(seed);tones=[]
        colored=2*10**(colored_at_100khz_dbc_hz/10)*1e10
        white=2*10**(floor_dbc_hz/10)
        for low,high in zip(edges[:-1],edges[1:]):
            f=math.sqrt(low*high)
            variance=colored*(1/low-1/high)+white*(high-low)
            transfer=(1.+0j if injection=='direct' else
                      1j*f/(loop_pole_hz+1j*f) if injection=='vco' else
                      loop_pole_hz/(loop_pole_hz+1j*f))
            tones.append((f,math.sqrt(2*variance)*abs(transfer),
                          rng.uniform(-math.pi,math.pi)+math.atan2(transfer.imag,transfer.real)))
        return cls(tuple(tones))
