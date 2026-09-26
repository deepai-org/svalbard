"""Divider arithmetic, pulse feedback and measured deterministic timing ripple."""
import cmath,copy,json,math
from fractions import Fraction
from chip_model import P
from fractional_pulse_pll import DividerSequence,FractionalPulsePLL

def counted_frequency_interval(start_count,end_count,window_s,prescale=16,
                               capture_error_counts=0):
    """Bound window-average frequency from monotonic prescaled counts.

    Each endpoint may have a bounded integer capture error. Counter wrap must
    already be resolved by the caller. The extra count bounds endpoint phase
    quantization; this measures mean frequency, never instantaneous phase quality.
    """
    if (type(start_count) is not int or type(end_count) is not int or
        end_count<start_count or type(prescale) is not int or prescale<1 or
        type(capture_error_counts) is not int or capture_error_counts<0 or
        not math.isfinite(window_s) or window_s<=0):
        raise ValueError('Invalid edge-count measurement')
    estimate=(end_count-start_count)*prescale/window_s
    bound=(1+2*capture_error_counts)*prescale/window_s
    return max(0.,estimate-bound),estimate+bound

class CountedAcquisition:
    """Candidate frequency acquisition, separate from phase/payload readiness.

    Captures are unwrapped integer prescaled counts on reference edges. The
    independent watchdog must be ticked even when reference edges stop. Counts
    may carry the declared endpoint error; reference accuracy bounds the window.
    """
    def __init__(self,target_hz,reference_hz=40e6,window_edges=20000,
                 prescale=16,capture_error_counts=1,reference_error_ppm=10.,
                 tolerance_ppm=100.,required_windows=2,watchdog_s=100e-9):
        if (not all(math.isfinite(x) and x>0 for x in
                    (target_hz,reference_hz,tolerance_ppm,watchdog_s)) or
            not math.isfinite(reference_error_ppm) or not 0<=reference_error_ppm<1e6 or
            any(type(x) is not int or x<1 for x in (window_edges,prescale,required_windows)) or
            type(capture_error_counts) is not int or capture_error_counts<0):
            raise ValueError('Invalid counted acquisition contract')
        self.target=target_hz;self.reference=reference_hz;self.window=window_edges
        self.prescale=prescale;self.capture_error=capture_error_counts
        self.reference_error=reference_error_ppm*1e-6;self.tolerance=tolerance_ppm*1e-6
        self.required=required_windows;self.watchdog=watchdog_s
        self.time=0.;self.last_edge=None;self.anchor=None;self.edges=0
        self.good=0;self.acquired=False;self.interval=None;self.measurements=0

    def tick(self,time):
        if not math.isfinite(time) or time<self.time:
            raise ValueError('Nonmonotonic acquisition time')
        self.time=time
        if self.last_edge is not None and time-self.last_edge>self.watchdog:
            self.acquired=False;self.good=0;self.anchor=None;self.edges=0

    def reference_edge(self,time,count):
        if type(count) is not int:
            raise ValueError('Integer count required')
        if self.last_edge is not None and time<=self.last_edge:
            raise ValueError('Reference edges must be strictly ordered')
        self.tick(time);self.last_edge=time
        if self.anchor is None:
            self.anchor=count;self.edges=0;return self.acquired
        self.edges+=1
        if self.edges==self.window:
            if count<self.anchor:
                self.acquired=False;self.good=0;self.anchor=None
                raise ValueError('Counter wrap must be resolved before capture')
            low,high=counted_frequency_interval(self.anchor,count,
                self.window/self.reference,self.prescale,self.capture_error)
            self.interval=(low*(1-self.reference_error),high*(1+self.reference_error))
            valid=(self.interval[0]>=self.target*(1-self.tolerance) and
                   self.interval[1]<=self.target*(1+self.tolerance))
            self.good=self.good+1 if valid else 0
            self.acquired=self.good>=self.required;self.measurements+=1
            self.anchor=count;self.edges=0
        return self.acquired

def run(rate,pll_class=FractionalPulsePLL,bandwidth_hz=1e6,*,noise_rms_hz=0.,noise_seed=830,fast_fraction=.5):
    ratio=Fraction(rate,40000000);d=pll_class.SEQUENCE_CLASS(ratio)
    counts=[d.step() for _ in range(2*ratio.denominator)]
    assert sum(counts)==2*ratio.numerator and d.accumulator==0
    assert all(0<n and d.low-1<=n<=d.low+2 for n in counts)
    from oscillator_noise import FrequencyNoise
    p=pll_class(rate_hz=rate,bandwidth_hz=bandwidth_hz,fast_fraction=fast_fraction)
    p.frequency_noise=FrequencyNoise.seeded(noise_rms_hz,seed=noise_seed)
    assert p.advance(40e-6)
    before=(p.phase,p.time,p.sequence.accumulator,p.sequence.emitted,p.sequence.total)
    target=p.phase+123.5;crossing=p.edge_time(target)
    assert before==(p.phase,p.time,p.sequence.accumulator,p.sequence.emitted,p.sequence.total)
    trial=copy.copy(p);assert trial.advance(crossing) and abs(trial.phase-target)<2e-8
    dense=copy.copy(p)
    start=p.time;initial=p.phase;points=[]
    for i in range(1,801):
        t=start+i/40e6;assert p.advance(t);points.append((t-start,p.phase-initial))
    slope=points[-1][1]/points[-1][0]
    residual=[phase-slope*t for t,phase in points]
    mean=sum(residual)/len(residual)
    rms=math.sqrt(sum((x-mean)**2 for x in residual)/len(residual))/rate
    ppm=(slope/rate-1)*1e6
    assert abs(ppm)<1000,ppm # Numerical tracking sanity, not a protocol tolerance.
    dense_points=[]
    for i in range(1,12801):
        t=start+i/(16*40e6);assert dense.advance(t)
        dense_points.append((t-start,dense.phase-initial))
    dense_slope=dense_points[-1][1]/dense_points[-1][0]
    dense_residual=[phase-dense_slope*t for t,phase in dense_points]
    center=sum(dense_residual)/len(dense_residual)
    dense_rms=math.sqrt(sum((x-center)**2 for x in dense_residual)/len(dense_residual))/rate
    assert abs(dense.phase-p.phase)<1e-6
    phasors=[cmath.exp(2j*math.pi*x) for x in dense_residual]
    carrier=sum(phasors)/len(phasors)
    phase_only_error=math.sqrt(sum(abs(z-carrier)**2 for z in phasors)/len(phasors))/abs(carrier)
    history=p.reference_history[-800:]
    assert len(history)==800
    phase_bad=sum(abs(x[1])>=250e-12 for x in history)
    frequency_bad=sum(abs(x[2])>=100e-6 for x in history)
    both_bad=sum(abs(x[1])>=250e-12 and abs(x[2])>=100e-6 for x in history)
    qualification=dict(reference_samples=len(history),phase_rejected=phase_bad,
        instantaneous_frequency_rejected=frequency_bad,both_rejected=both_bad,
        phase_peak_s=max(abs(x[1]) for x in history),
        instantaneous_frequency_peak_ppm=max(abs(x[2]) for x in history)*1e6,
        instantaneous_frequency_rms_ppm=math.sqrt(sum(x[2]**2 for x in history)/len(history))*1e6,
        consecutive_valid_samples_required=8,phase_limit_s=250e-12,
        instantaneous_frequency_limit_ppm=100.)
    return dict(loop_class=pll_class.__name__,bandwidth_hz=bandwidth_hz,
        qualification_diagnostic=qualification,
        counted_mean_frequency_intervals_hz={str(scale):
            counted_frequency_interval(math.floor(initial/scale),
                math.floor(p.phase/scale),p.time-start,scale)
            for scale in (1,16)},
        noise_rms_hz=noise_rms_hz,noise_seed=noise_seed,fast_fraction=fast_fraction,
        observation_locked_fraction=sum(bool(x[4]) for x in p.reference_history[-800:])/800,
        loop_filter=p.filter.metrics(),
        phase_only_relative_rms=phase_only_error,dense_timing_rms_s=dense_rms,
        dense_timing_peak_to_peak_s=(max(dense_residual)-min(dense_residual))/rate,
        dense_observation_step_s=1/(16*40e6),target_hz=rate,divider_observation_cycles=len(counts),integer_counts=counts,mean_frequency_error_ppm=ppm,
        detrended_timing_rms_s=rms,detrended_timing_peak_to_peak_s=(max(residual)-min(residual))/rate,
        final_locked=p.locked,compliance_margin_v=p.metrics()['minimum_compliance_margin_v'])

def clock_filter_tradeoff_screen(settings,*,rate_hz=2437000000,reference_hz=40e6,noise_rms_hz=100000.,
        noise_seed=831,warmup_s=20e-6,samples=4096,sample_hz=160e6,extra_frequency_tones=()):
    """Bounded actual-edge candidate screen; never a payload acceptance gate."""
    import numpy as np
    from shaped_fractional_pll import ThirdOrderFractionalPLL
    from oscillator_noise import FrequencyNoise
    if type(samples) is not int or samples<128 or not all(math.isfinite(x) and x>0 for x in (warmup_s,sample_hz)):
        raise ValueError('Positive clock observation geometry required')
    rows=[]
    for bandwidth,fast_fraction in settings:
        clock=ThirdOrderFractionalPLL(rate_hz=rate_hz,reference_hz=reference_hz,bandwidth_hz=bandwidth,fast_fraction=fast_fraction)
        clock.set_noise(0.,FrequencyNoise(FrequencyNoise.seeded(noise_rms_hz,seed=noise_seed).tones+tuple(extra_frequency_tones)))
        times=warmup_s+np.arange(samples)/sample_hz;phase=[]
        for time in times:
            if not clock.advance(float(time)):break
            phase.append(2*math.pi*(clock.phase-clock.rate*time))
        row=dict(bandwidth_hz=bandwidth,fast_fraction=fast_fraction,
                 completed=len(phase)==samples,fault=clock.fault,filter=clock.filter.metrics())
        if row['completed']:
            # Diagnostic removal of constant phase and average frequency, not
            # a claim that a practical payload observer has estimated either.
            phase=np.array(phase);fit=np.polyfit(times-times[0],phase,1)
            residual=phase-np.polyval(fit,times-times[0])
            spectrum=abs(np.fft.rfft(residual*np.hanning(samples)))
            peak=1+int(np.argmax(spectrum[1:]))
            row.update(phase_rms_rad=float(np.std(residual)),
                fitted_frequency_error_hz=float(fit[0]/(2*math.pi)),
                strongest_bin_hz=peak*sample_hz/samples)
        rows.append(row)
    return dict(cases=rows,rate_hz=rate_hz,reference_hz=reference_hz,noise_rms_hz=noise_rms_hz,
        noise_seed=noise_seed,warmup_s=warmup_s,samples=samples,sample_hz=sample_hz,extra_frequency_tones=extra_frequency_tones,
        scope='Actual fractional divider/pump/filter with finite-tone oscillator noise. Unloaded clock only; diagnostic affine detrending, one seed/window, no supply/packet/acquisition envelope or physical qualification.')


def main():
    rows=[run(r) for r in (2412000000,2437000000)]
    (P/'evidence/connected-fractional-pulse.json').write_text(json.dumps(dict(status='passed',cases=rows,
        complete_architecture=False,physical_qualification=False,
        limitations=['Passing validates integer-divider arithmetic and simulation, not RF quality or lock qualification.',
        'First-order periodic modulation can create deterministic spurs; no noise shaping or dither.',
        'Loop filter uses the lower integer-band design; tuning-gain variation and divider hardware are unqualified.']),indent=2)+'\n')
    print('Fractional pulse measurements:',rows,flush=True)
if __name__=='__main__':main()
