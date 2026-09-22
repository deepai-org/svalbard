"""Nonloading RF output observation against an independent nominal carrier."""
import copy,cmath,math
import numpy as np
from tx_output_stage import output_envelope

def tx_components(c,carrier_hz):
    time=c.time
    if time<c.tx.time or time<c.rf_pll.time:raise ValueError('Observation precedes model state')
    # Forecast copies only; do not drive either oscillator or analog filter.
    p=copy.copy(c.rf_pll);p.advance(time)
    baseband=(c.tx.output_value(time) if hasattr(c.tx,'output_value') else
        c.tx.held+(c.tx.filtered-c.tx.held)*math.exp(-c.tx.pole*(time-c.tx.time)))
    phase=math.remainder(p.output_phase_cycles-carrier_hz*time,1.)
    return baseband,cmath.exp(1j*(2*math.pi*phase+c.rf_tx_phase))

def observe_tx(c,carrier_hz):
    baseband,rotation=tx_components(c,carrier_hz)
    value=complex(output_envelope(np.array([baseband]),np.array([rotation]),**getattr(c,'tx_output_parameters',{}))[0])
    return value*(c.tx_pad_transfer(c.time) if hasattr(c,'tx_pad_transfer') else 1.)

def observed(base,carrier_hz,instances):
 class Observed(base):
    def __init__(self,**kwargs):
        self.tx_observations=[];self.tx_component_observations=[];self.tx_pad_transfers=[];super().__init__(**kwargs);instances.append(self)
    def feed(self,word,epoch,time):
        result=super().feed(word,epoch,time)
        if not getattr(self,'tx_observe_enabled',True):return result
        baseband,rotation=tx_components(self,carrier_hz)
        value=complex(output_envelope(np.array([baseband]),np.array([rotation]),**getattr(self,'tx_output_parameters',{}))[0])
        transfer=self.tx_pad_transfer(self.time) if hasattr(self,'tx_pad_transfer') else 1.
        self.tx_pad_transfers.append(transfer)
        value*=transfer
        self.tx_observations.append((self.time,value))
        self.tx_component_observations.append((baseband,rotation))
        return result
 return Observed

def spectrum(times,values):
    t=np.asarray(times);v=np.asarray(values);dt=float(np.median(np.diff(t)))
    if len(v)<256 or dt<=0 or not np.allclose(np.diff(t),dt,rtol=0,atol=1e-15):
        raise ValueError('Spectrum requires a uniform nontrivial observation grid')
    w=np.hanning(len(v));power=abs(np.fft.fft(v*w))**2
    hz=np.fft.fftfreq(len(v),dt);inside=abs(hz)<=10e6
    carrier_power=float(power[inside].sum());outside=float(power[~inside].sum())
    if carrier_power<=0:raise ValueError('Missing transmit signal')
    return dict(sample_rate_hz=1/dt,samples=len(v),bin_spacing_hz=1/(len(v)*dt),
        analysis_window='Hann; finite burst including launch transient',channel_half_width_hz=10e6,
        outside_to_inside_db=10*math.log10(max(outside/carrier_power,1e-300)),
        scope='All observed frequencies outside +/-10MHz up to observation Nyquist; not a protocol emission mask')
