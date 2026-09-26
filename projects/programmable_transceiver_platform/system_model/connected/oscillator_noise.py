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

    def crossing_error(self,ideal_times,carrier_hz):
        """Solve omega*t + phase(t) = omega*ideal_time for bounded phase slope."""
        import numpy as np
        if not math.isfinite(carrier_hz) or carrier_hz<=0:
            raise ValueError('Positive carrier required')
        if sum(abs(a)*f/carrier_hz for f,a,_ in self.tones)>=.5:
            raise ValueError('Monotonic contractive phase slope required')
        times=np.asarray(ideal_times,float)
        omega=2*math.pi*carrier_hz
        error=-self.phase(times)/omega
        for _ in range(40):error=-self.phase(times+error)/omega
        if np.any(abs(error+self.phase(times+error)/omega)>1e-16):
            raise ValueError('LO crossing solution did not converge')
        return error

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


def loaded_clock_input_phase(carrier_hz,*,cap_f=3e-12,bond_l_h=2e-9,
                             termination_ohm=None,seed=1831,
                             receiver_noise_v=1e-3,downstream_stage_rms_s=.3e-12,
                             source_peak_v=.5,threshold_v=.020,am_depth=.1,noise_bins=32):
    """Assigned external-input RLC, threshold AM conversion and additive noise.

    Source defaults to 0.5 V peak Thevenin/50 ohms. Finite spectral noise uses the same
    1 kHz–8 MHz band as the joined source; 1 MHz AM retains twenty harmonics.
    Static transfer delay is omitted. This is not a transistor receiver model.
    """
    import numpy as np
    if not all(math.isfinite(v) and v>0 for v in (carrier_hz,cap_f,bond_l_h)):
        raise ValueError('Positive finite carrier and input parasitics required')
    if termination_ohm is not None and (not math.isfinite(termination_ohm) or termination_ohm<=0):
        raise ValueError('Positive termination or high impedance required')
    if not all(math.isfinite(v) and v>=0 for v in (receiver_noise_v,downstream_stage_rms_s)):
        raise ValueError('Finite nonnegative input/distribution noise required')
    if type(noise_bins) is not int or not 1<=noise_bins<=4096:
        raise ValueError('Bounded positive additive-noise spectral resolution required')
    omega=2*math.pi*carrier_hz
    admittance=1j*omega*cap_f+(0 if termination_ohm is None else 1/termination_ohm)
    transfer=1/(1+(50.2+1j*omega*bond_l_h)*admittance)
    if (not all(math.isfinite(v) for v in (source_peak_v,threshold_v,am_depth))
            or source_peak_v<=0 or not 0<=am_depth<1):
        raise ValueError('Finite positive source, finite threshold and bounded AM required')
    peak=source_peak_v*abs(transfer);threshold=threshold_v
    if (1-am_depth)*peak<=abs(threshold) or (1+am_depth)*peak>.6:
        raise ValueError('Assigned input crossing/amplitude envelope exceeded')
    grid=np.arange(512)*2*math.pi/512
    amplitude=peak*(1+am_depth*np.sin(grid))
    crossing=np.arcsin(threshold/amplitude)/omega
    crossing-=crossing.mean()
    coeff=np.fft.rfft(crossing)/len(crossing)
    delay=[(k*1e6,2*float(abs(coeff[k])),float(np.angle(coeff[k]))) for k in range(1,21)]
    am_phase=tuple((f,-omega*a,p) for f,a,p in delay)
    # Stationary equivalent: average input noise/slew variance over AM cycle.
    receiver_variance=float(np.mean(receiver_noise_v**2/(omega**2*(amplitude**2-threshold**2))))
    downstream_variance=2*downstream_stage_rms_s**2
    rng=np.random.default_rng(seed)
    edges=np.geomspace(1e3,8e6,noise_bins+1)
    for lo,hi in zip(edges[:-1],edges[1:]):
        variance=(receiver_variance+downstream_variance)*(hi-lo)/(8e6-1e3)
        delay.append((math.sqrt(lo*hi),math.sqrt(2*variance),float(rng.uniform(-math.pi,math.pi))))
    phase=PhaseNoise(tuple((f,-omega*a,p) for f,a,p in delay))
    return phase,dict(carrier_hz=carrier_hz,cap_f=cap_f,bond_l_h=bond_l_h,
        termination_ohm=termination_ohm,receiver_peak_v=peak,
        source_peak_v=source_peak_v,threshold_v=threshold_v,am_depth=am_depth,
        additive_noise_bins=noise_bins,
        phase_components=dict(am=am_phase,additive=phase.tones[len(am_phase):]),
        receiver_noise_v=receiver_noise_v,downstream_stage_rms_s=downstream_stage_rms_s,
        equivalent_additive_ssb_floor_dbc_hz=(10*math.log10(omega**2*(receiver_variance+downstream_variance)/(2*(8e6-1e3))) if receiver_variance+downstream_variance>0 else None),
        receiver_random_time_rms_s=math.sqrt(receiver_variance),
        downstream_random_time_rms_s=math.sqrt(downstream_variance),
        am_time_rms_s=math.sqrt(2*float(sum(abs(coeff[1:21])**2))),
        phase_variance_rad2=phase.variance_rad2,seed=seed,
        limitations=['Source amplitude, receiver noise, threshold offset and AM depth are explicit hypotheses, not a qualified input circuit.',
            'Two declared downstream noise allocations; stationary white-equivalent noise in 1 kHz–8 MHz.',
            'Input AM at 1 MHz; cyclostationary additive-noise modulation omitted.',
            'Source PM passes with unity gain; loaded sideband dispersion, stage power/startup and supply correlation unqualified.',
            'Absolute static propagation delay omitted; no latency or input-circuit qualification.'])
