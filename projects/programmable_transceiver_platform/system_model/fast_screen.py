"""Fast complex-envelope RX sensitivity screen; never an implementation gate.

No GHz carrier timesteps. Uncharacterized values are explicit scenario inputs.
This first increment covers RX gain, bandwidth, clipping, LO phase, reference
scale error and quantization. Other whole-chip paths remain explicit gaps.
"""
import hashlib
import itertools
import json
import time
from pathlib import Path
import numpy as np

P = Path(__file__).resolve().parents[1]

def lowpass(x, fs, bandwidth):
    a = np.exp(-2*np.pi*bandwidth/fs)
    y = np.empty_like(x); state = 0j
    for k, value in enumerate(x):
        state = a*state+(1-a)*value
        y[k] = state
    return y

def convert(x, span, bits=8):
    step = span/(2**bits)
    return (np.clip(np.floor((x+span/2)/step),0,2**bits-1)+.5)*step-span/2

def reference_response(charge, fs, capacitance, resistance, decision_delay):
    """Linear reservoir with signed impulse withdrawal then exponential recovery.

    Positive charge lowers span. This is a differential equivalent, not two
    physical rails. No current limiting or amplifier poles are represented.
    """
    assert capacitance>0 and resistance>0 and 0<=decision_delay<=1/fs
    tau=resistance*capacitance
    recovery=np.exp(-1/(fs*tau)); sample=np.exp(-decision_delay/tau)
    error=0.; span=np.empty(len(charge))
    for k,q in enumerate(charge):
        error=error*recovery-q/capacitance
        span[k]=1+error*sample
    return span

def clock_phase(frequency_error_hz, fs, correction_hz=0):
    """Type-I linear phase feedback: dphi/dt=2*pi*df-2*pi*fc*phi.

    Exact held-disturbance update; no acquisition, saturation or type-II claim.
    """
    assert correction_hz>=0
    if correction_hz==0: return 2*np.pi*np.cumsum(frequency_error_hz)/fs
    a=np.exp(-2*np.pi*correction_hz/fs);state=0.;out=[]
    for df in frequency_error_hz:
        state=a*state+(1-a)*df/correction_hz
        out.append(state)
    return np.array(out)

def run(gain, bandwidth, phase_rms, reference_fraction, seed=123, rail=None, supply=None, activity_trace=None, fs=40e6, bits=8):
    n=4096; t=np.arange(n)/fs
    # Two in-band tones, total maximum input envelope 1 mV.
    source=.0005*(np.exp(2j*np.pi*3e6*t)+np.exp(2j*np.pi*7e6*t))
    rng=np.random.default_rng(seed)
    phase=rng.normal(0,phase_rms,n)
    ideal=source*gain
    gain_factor=np.ones(n); dv=np.zeros(n)
    if supply is not None:
        # Held activity current through shared first-order supply impedance.
        activity=.5+.5*np.cos(2*np.pi*1e6*t) if activity_trace is None else np.asarray(activity_trace)
        assert activity.shape==(n,) and np.isfinite(activity).all() and np.all(activity>=0)
        dv=-lowpass((supply['load_a']*activity).astype(complex),fs,supply['pole_hz']).real*supply['resistance_ohm']
        # Voltage-sensitive oscillator integrated to phase, no PLL correction yet.
        phase=phase+clock_phase(dv*supply['vco_hz_per_v'],fs,supply.get('correction_hz',0))
        gain_factor=1+supply['gain_per_v']*dv
    analog=lowpass(ideal*gain_factor*np.exp(1j*phase),fs,bandwidth)
    # Signed periodic reference variation: sensitivity stimulus, not fitted rail model.
    span=1+reference_fraction*np.sin(2*np.pi*1e6*t)
    if rail is not None:
        # Proxy for signal-dependent switching, not an extracted SAR charge law.
        activity=np.abs(np.diff(analog.real,prepend=analog.real[0]))+np.abs(np.diff(analog.imag,prepend=analog.imag[0]))
        charge=rail['charge_c']*(1+activity)
        span=reference_response(charge,fs,rail['capacitance_f'],rail['resistance_ohm'],rail['decision_delay_s'])
    if np.any(span<=0):
        return dict(gain=gain,rail=rail,status='invalid_reference_span')
    span=span+dv*(supply['reference_v_per_v'] if supply else 0)
    if np.any(span<=0): return dict(status='invalid_reference_span',supply=supply)
    clipped=(abs(analog.real)>=span/2)|(abs(analog.imag)>=span/2)
    # Reconstruct nominal-voltage codes, exposing gain error from changing reference.
    output=convert(analog.real/span,1,bits)+1j*convert(analog.imag/span,1,bits)
    sl=slice(256,None); ref=ideal[sl]; out=output[sl]
    coefficient=np.vdot(ref,out)/np.vdot(ref,ref)
    error=out-coefficient*ref
    return dict(sample_rate_hz=fs,bits_per_component=bits,gain=gain,bandwidth_hz=bandwidth,phase_rms_rad=phase_rms,
        supply=supply,supply_min_v=float(dv.min()),supply_max_v=float(dv.max()),rail=rail,span_min_v=float(span.min()),span_max_v=float(span.max()),reference_fraction=reference_fraction,clipped_fraction=float(clipped[sl].mean()),
        fitted_gain_magnitude=float(abs(coefficient)),
        residual_evm=float(np.linalg.norm(error)/max(np.linalg.norm(coefficient*ref),1e-30)))

def iq_transform(x, gain_error, phase_error):
    return x.real+1j*(1+gain_error)*x.imag*np.exp(1j*phase_error)

def compress(x, saturation):
    # Radial soft limiter, preserving phase; saturation is envelope volts.
    return x/np.sqrt(1+(np.abs(x)/saturation)**2)

def loopback(amplitude, gain_error, phase_error, saturation, fs=40e6, bits=8, oversample=16):
    assert fs>14e6 and bits>0 and isinstance(oversample,int) and oversample>=1
    t=np.arange(4096)/fs
    intended=amplitude/2*(np.exp(2j*np.pi*3e6*t)+np.exp(2j*np.pi*7e6*t))
    dac=convert(intended.real,1,bits)+1j*convert(intended.imag,1,bits)
    held=np.repeat(dac,oversample)
    tx=compress(iq_transform(lowpass(held,fs*oversample,12e6),gain_error,phase_error),saturation)
    # Deliberate external loopback attenuator and receiver gain, not on-chip leakage.
    received=lowpass(tx*.01*100,fs*oversample,20e6)[oversample-1::oversample]
    adc=convert(received.real,1,bits)+1j*convert(received.imag,1,bits)
    sl=slice(256,None); ref=intended[sl]; out=adc[sl]
    gain=np.vdot(ref,out)/np.vdot(ref,ref)
    return dict(oversample=oversample,adc_sample_phase_ui=1.0,sample_rate_hz=fs,bits_per_component=bits,amplitude_v=amplitude,iq_gain_error=gain_error,
        iq_phase_error_rad=phase_error,saturation_v=saturation,
        dac_clipped_fraction=float(np.mean((abs(intended.real)>=.5)|(abs(intended.imag)>=.5))),
        adc_clipped_fraction=float(np.mean((abs(received.real)>=.5)|(abs(received.imag)>=.5))),
        fitted_gain_magnitude=float(abs(gain)),
        residual_evm=float(np.linalg.norm(out-gain*ref)/np.linalg.norm(gain*ref)))

def main():
    start=time.monotonic()
    # Mathematical controls, independent of an expected candidate ranking.
    assert np.allclose(lowpass(np.ones(100,dtype=complex),1e6,1e5)[-1],1)
    ramp=np.linspace(-.49,.49,1001)
    assert np.max(abs(convert(ramp,1)-ramp))<=1/512+1e-15
    assert np.all(np.diff(convert(ramp,1))>=0)
    scenarios=[run(*v) for v in itertools.product([8,64,256,1024],[8e6,20e6],[0,.03,.1],[-.08,0,.08])]
    # Independent closed-form controls: impulse, signed symmetry and zero load.
    q=np.array([1e-12,0.,0.]); fs=40e6; cap=100e-12; resistance=100.
    expected=1-.01*np.exp(-np.arange(3)/(fs*cap*resistance))
    assert np.allclose(reference_response(q,fs,cap,resistance,0),expected,rtol=0,atol=1e-14)
    assert np.allclose(reference_response(q,fs,cap,resistance,0)+reference_response(-q,fs,cap,resistance,0),2)
    assert np.array_equal(reference_response(q*0,fs,cap,resistance,0),np.ones(3))
    rail_scenarios=[run(256,20e6,0,0,rail=dict(charge_c=q,capacitance_f=c,resistance_ohm=r,decision_delay_s=d))
        for q,c,r,d in itertools.product([-10e-12,0,10e-12],[50e-12,200e-12],[20,200],[0,5e-9])]
    # Independent identity, bound and phase-preservation controls.
    z=np.array([0,1+2j,-3+4j],dtype=complex)
    assert np.array_equal(iq_transform(z,0,0),z)
    limited=compress(z,.3)
    assert np.all(abs(limited)<.3)
    assert np.allclose((limited[1:]/z[1:]).imag,0)
    loopback_scenarios=[loopback(*v) for v in itertools.product([.05,.4,.8],[-.1,0,.1],[-.1,0,.1],[.3,3.])]
    supply_scenarios=[run(256,20e6,0,0,supply=dict(load_a=.01,pole_hz=2e6,
        resistance_ohm=r,vco_hz_per_v=k,gain_per_v=g,reference_v_per_v=.1))
        for r,k,g in itertools.product([0,1,5],[-1e8,1e8],[-1,1])]
    control=run(256,20e6,0,0)
    assert all(c['residual_evm']==control['residual_evm'] for c in supply_scenarios if c['supply']['resistance_ohm']==0)
    df=np.ones(64)*1e3; fs=40e6; fc=1e6
    assert np.allclose(clock_phase(df,fs,fc),1e3/fc*(1-np.exp(-2*np.pi*fc*(np.arange(64)+1)/fs)),atol=1e-14,rtol=0)
    assert np.allclose(clock_phase(-df,fs,fc),-clock_phase(df,fs,fc))
    assert np.allclose(clock_phase(df,fs),2*np.pi*1e3*(np.arange(64)+1)/fs)
    feedback_scenarios=[run(256,20e6,0,0,supply=dict(load_a=.01,pole_hz=2e6,
        resistance_ohm=1,vco_hz_per_v=k,gain_per_v=1,reference_v_per_v=.1,correction_hz=fc))
        for k,fc in itertools.product([-1e8,1e8],[0,1e5,1e6,5e6])]
    report=dict(feedback_scenarios=feedback_scenarios,supply_scenarios=supply_scenarios,loopback_scenarios=loopback_scenarios,rail_scenarios=rail_scenarios,status='exploratory_not_qualified',whole_chip_schematic_ready=False,
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        runtime_seconds=time.monotonic()-start,scenarios=scenarios,
        assumptions=['All sweep values are hypothetical, not guaranteed process bounds.',
        '40MS/s complex envelope; 8-bit nominal 1V converters; not current circuit behavior.',
        'White independent LO phase samples are sensitivity only, not a phase-noise spectrum.',
        'EVM removes one complex gain only; two-tone test is not Wi-Fi compliance.',
        'Legacy sinusoidal cases remain; rail cases use hypothetical signal-dependent signed charge and a linear differential reservoir.'],
        missing=['TX spectral images, PA/load interaction and modulation compliance','wired TX/RX/CDR','PLL acquisition and colored noise',
        'two physical reference rails, current limits and shared supply dynamics','host transport','bias/startup',
        'RF noise, blockers and calibrated RX nonlinearities/IQ imbalance','area/power integration'])
    (P/'evidence/fast-system-screen.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'{len(scenarios)+len(rail_scenarios)+len(loopback_scenarios)+len(supply_scenarios)+len(feedback_scenarios)} scenarios in {report["runtime_seconds"]:.3f}s; exploratory RF envelope paths')
if __name__=='__main__': main()
