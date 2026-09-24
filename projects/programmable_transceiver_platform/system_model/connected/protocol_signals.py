"""FPGA-supplied PHY symbol fixtures, not packet/MAC implementations.

Complex envelopes use physical seconds and retain phase across sample boundaries.
HE DATA, Bluetooth modulated payloads, 802.15.4 supplied chips and LoRa chirps
exercise analog requirements without moving protocol engines onto the chip.
"""
from dataclasses import dataclass
import math
import numpy as np
from scipy.signal import lfilter


@dataclass
class Waveform:
    samples: np.ndarray
    sample_hz: float
    kind: str
    symbols: np.ndarray
    metadata: dict

    def __post_init__(self):
        self.samples=np.array(self.samples,dtype=complex,copy=True)
        self.symbols=np.array(self.symbols,copy=True)
        if (not math.isfinite(self.sample_hz) or self.sample_hz<=0 or
                self.samples.ndim!=1 or not len(self.samples) or
                not np.all(np.isfinite(self.samples))):
            raise ValueError('Finite nonempty sampled waveform required')
        self.samples.flags.writeable=False
        self.symbols.flags.writeable=False

    @property
    def duration(self):return len(self.samples)/self.sample_hz

    def value(self,time):
        """Zero-order hold; caller must split integration at sample boundaries."""
        if not math.isfinite(time):raise ValueError('Nonfinite waveform time')
        i=math.floor(time*self.sample_hz)
        return complex(self.samples[i]) if 0<=i<len(self.samples) else 0j


def gfsk(bits,rate=1e6,h=.5,fs=20e6):
    bits=np.asarray(bits,int)
    if bits.ndim!=1 or not len(bits) or np.any((bits!=0)&(bits!=1)):
        raise ValueError('GFSK binary symbols required')
    sps=round(fs/rate)
    if sps<4 or abs(sps*rate-fs)>1e-6 or not 0<h<=1:raise ValueError('GFSK sample/rate envelope')
    # Gaussian frequency pulse, BT=.5, normalized DC response; finite +/-2 T.
    t=np.arange(-2*sps,2*sps+1)/sps
    pulse=np.exp(-2*(math.pi*.5*t)**2/math.log(2));pulse/=pulse.sum()
    nrz=np.repeat(2*bits-1,sps)
    frequency=np.convolve(nrz,pulse)*h*rate/2
    phase=2*math.pi*np.r_[0.,np.cumsum(frequency[:-1])]/fs
    return Waveform(np.exp(1j*phase),fs,'gfsk',bits,
                    dict(sps=sps,delay=2*sps,h=h,symbol_rate=rate,bt=.5))


def rrc(sps,alpha=.4,span=8):
    t=np.arange(-span*sps,span*sps+1)/sps
    h=np.empty_like(t)
    for i,x in enumerate(t):
        if abs(x)<1e-12:h[i]=1+alpha*(4/math.pi-1)
        elif abs(abs(x)-1/(4*alpha))<1e-12:
            h[i]=alpha/math.sqrt(2)*((1+2/math.pi)*math.sin(math.pi/(4*alpha))+(1-2/math.pi)*math.cos(math.pi/(4*alpha)))
        else:h[i]=(math.sin(math.pi*x*(1-alpha))+4*alpha*x*math.cos(math.pi*x*(1+alpha)))/(math.pi*x*(1-(4*alpha*x)**2))
    return h/np.sqrt(h@h)


def edr(symbols,order=4,fs=20e6):
    symbols=np.asarray(symbols,int);sps=round(fs/1e6)
    if order not in (4,8) or sps<4 or sps*1e6!=fs or np.any((symbols<0)|(symbols>=order)):
        raise ValueError('EDR phase-symbol envelope')
    increments=2*math.pi*symbols/order+(math.pi/4 if order==4 else 0)
    points=np.exp(1j*np.r_[0,np.cumsum(increments)])
    impulse=np.zeros(len(points)*sps,complex);impulse[::sps]=points
    pulse=rrc(sps)
    return Waveform(np.convolve(impulse,pulse),fs,'edr',symbols,
                    dict(sps=sps,pulse=pulse.tolist(),order=order))


def oqpsk(chips,fs=20e6):
    chips=np.asarray(chips,int);tc=round(fs/2e6)
    if len(chips)%2 or tc<2 or tc*2e6!=fs or np.any((chips!=0)&(chips!=1)):
        raise ValueError('Even binary 802.15.4 chip stream required')
    # Even/odd chips feed I/Q; each half-sine lasts 2Tc; Q is delayed Tc.
    pulse=np.sin(math.pi*np.arange(2*tc)/(2*tc))
    out=np.zeros((len(chips)+2)*tc,complex)
    for i,bit in enumerate(chips):out[i*tc:i*tc+2*tc]+=(2*bit-1)*(1 if i%2==0 else 1j)*pulse
    return Waveform(out,fs,'oqpsk',chips,dict(tc=tc,chip_hz=2e6,spreading='FPGA supplies DSSS chips'))


def he20(symbols,gi_us=.8):
    """HE20 BPSK DATA modulation: no preamble, FEC, interleaver or pilot polarity sequence."""
    if gi_us not in (.8,1.6,3.2):raise ValueError('HE guard interval')
    pilots=np.array([-116,-90,-48,-22,22,48,90,116])
    active=np.r_[np.arange(-122,-1),np.arange(2,123)]
    data=np.setdiff1d(active,pilots)
    bits=np.asarray(symbols,int)
    if bits.size%234 or np.any((bits!=0)&(bits!=1)):raise ValueError('234 BPSK data tones per HE symbol')
    cp=round(20*gi_us);out=[]
    for row in bits.reshape(-1,234):
        bins=np.zeros(256,complex);bins[data%256]=2*row-1;bins[pilots%256]=1
        z=np.fft.ifft(bins)*256/math.sqrt(242)
        out.extend(np.r_[z[-cp:],z])
    return Waveform(out,20e6,'he20',bits,dict(cp=cp,data=data.tolist(),pilots=pilots.tolist(),fft=256))


def lora(symbols,sf=7,bandwidth=812500.,oversample=1):
    if not 5<=sf<=12 or bandwidth not in (203125.,406250.,812500.,1625000.):
        raise ValueError('2.4 GHz chirp profile envelope')
    m=1<<sf;symbols=np.asarray(symbols,int)
    if np.any((symbols<0)|(symbols>=m)):raise ValueError('Chirp symbol range')
    if type(oversample) is not int or not 1<=oversample<=32:
        raise ValueError('Integer chirp oversampling from 1 through 32 required')
    n=np.arange(m*oversample)/oversample
    # Integrate frequency with an explicit wrap at +BW/2. At integer n this
    # equals the legacy Fs=BW fixture; between samples it stays in-band.
    samples=np.concatenate([np.exp(2j*math.pi*(n*n/(2*m)+(k/m-.5)*n-
        np.maximum(n-(m-k),0))) for k in symbols])
    return Waveform(samples,bandwidth*oversample,'lora',symbols,
                    dict(sf=sf,bandwidth=bandwidth,oversample=oversample))


def decisions(w,samples=None):
    """Independent observation operations; never read w.symbols for decoding."""
    z=np.asarray(w.samples if samples is None else samples,complex);m=w.metadata
    if w.kind=='gfsk':
        freq=np.angle(z[1:]*z[:-1].conj())
        n=(len(z)-4*m['sps'])//m['sps']
        return np.array([np.mean(freq[m['delay']+i*m['sps']+m['sps']//4:m['delay']+i*m['sps']+3*m['sps']//4])>0 for i in range(n)],int)
    if w.kind=='edr':
        p=np.asarray(m['pulse']);matched=np.convolve(z,p[::-1])
        points=matched[len(p)-1:len(z):m['sps']]
        # Filter tails contain no new symbols; count from transmit duration.
        count=(len(z)-len(p)+1)//m['sps'];points=points[:count]
        phase=np.angle(points[1:]*points[:-1].conj())-(math.pi/4 if m['order']==4 else 0)
        return np.rint(phase*m['order']/(2*math.pi)).astype(int)%m['order']
    if w.kind=='oqpsk':
        tc=m['tc'];count=len(z)//tc-2
        return np.array([(z[(i+1)*tc].real if i%2==0 else z[(i+1)*tc].imag)>0 for i in range(count)],int)
    if w.kind=='he20':
        frames=z.reshape(-1,256+m['cp']);bins=np.fft.fft(frames[:,m['cp']:],axis=1)
        return (bins[:,np.asarray(m['data'])%256].real>0).astype(int).ravel()
    if w.kind=='lora':
        z=z[::m.get('oversample',1)]
        n=1<<m['sf'];t=np.arange(n)/n
        reference=np.exp(-1j*math.pi*n*(t*t-t))
        return np.argmax(abs(np.fft.fft(z.reshape(-1,n)*reference,axis=1)),axis=1)
    raise ValueError('Unknown waveform')


def fixture(profile,variant='',seed=81):
    rng=np.random.default_rng(seed)
    if profile=='wifi_he20':return he20(rng.integers(0,2,234*4))
    if profile=='bluetooth_le':
        rate=2e6 if variant=='2m' else 1e6
        # Coded variants exercise the 1 Msym/s radio. FEC belongs to external FPGA.
        bits=rng.integers(0,2,64)
        if variant=='s8':bits=np.concatenate([([1,1,0,0] if b else [0,0,1,1]) for b in bits])
        if variant not in ('','1m','2m','s2','s8'):raise ValueError('LE variant')
        w=gfsk(bits,rate);w.metadata['coding_scope']='supplied coded symbols; FEC/packets not implemented'
        return w
    if profile=='bluetooth_br_edr':
        if variant in ('','br'):return gfsk(rng.integers(0,2,64),h=.32)
        if variant not in ('edr2','edr3'):raise ValueError('BR/EDR variant')
        order=4 if variant=='edr2' else 8
        return edr(rng.integers(0,order,64),order)
    if profile=='ieee802154_24':return oqpsk(rng.integers(0,2,32*8))
    if profile=='lora_24':return lora(rng.integers(0,128,8))
    raise ValueError('Profile has no RF waveform')


def receiver_projection(w,poles,weights,bits=12,amplitude=.2,phase_rad=None,frontend=None,gain=1.,sample_stride=1):
    """Fast reduction of canonical RX filter with frozen rails and uniform sampling.

    Does not acquire clocks or run host queues. No fitted/ideal LO correction.
    Returns actual quantized output and clipping count, not a compliance score.
    """
    if bits not in (8,12) or not 0<amplitude<=1 or isinstance(gain,bool) or gain not in (.5,1.,2.):raise ValueError('ADC projection envelope')
    if type(sample_stride) is not int or sample_stride<1:raise ValueError("Positive integer ADC sampling stride required")
    x=amplitude*w.samples
    if phase_rad is not None:
        phase=np.asarray(phase_rad)
        if phase.shape!=x.shape or not np.all(np.isfinite(phase)):raise ValueError('LO phase history')
        x=x*np.exp(-1j*phase)
    out=np.zeros_like(x)
    for pole,weight in zip(poles,weights):
        a=np.exp(-pole/w.sample_hz)
        out+=weight*lfilter([1-a],[1,-a],x)
    out=out[sample_stride-1::sample_stride]*gain
    if frontend is not None and (frontend.g!=0 or frontend.p!=0 or frontend.sat is not None or frontend.noise!=0):
        # Snapshot the same configured frontend used by canonical convert_adc.
        # Projection must not consume live RNG/state or alter chip time.
        import copy
        observer=copy.deepcopy(frontend)
        out=np.asarray([observer.sample(complex(value)) for value in out])
    scale=2**(bits-1)
    clipped=int(np.count_nonzero((abs(out.real)>1)|(abs(out.imag)>1)))
    quant=lambda y:np.clip(np.rint(y*scale),-scale,scale-1)/scale
    return quant(out.real)+1j*quant(out.imag),clipped


def transmitter_projection(w,reconstruction,output_parameters,bits=12,amplitude=.1,phase_rad=None):
    """Frozen-reference DAC/reconstruction/modulator reduction of canonical TX.

    Returns pre-pad envelope; finite output network and supply pulling remain in
    the coupled model, not silently replaced by this diagnostic projection.
    """
    from tx_output_stage import output_envelope
    if bits not in (8,12) or not 0<amplitude<=1:raise ValueError('DAC projection envelope')
    scale=2**(bits-1)
    q=lambda z:np.clip(np.rint(z*scale),-scale,scale-1)/scale
    x=amplitude*w.samples;x=q(x.real)+1j*q(x.imag)
    out=np.zeros_like(x)
    for pole,residue in zip(reconstruction.modal_poles,reconstruction.residues):
        a=np.exp(pole*reconstruction.scale/w.sample_hz)
        out+=residue*lfilter([(a-1)/pole],[1,-a],x)
    phases=np.zeros(len(out)) if phase_rad is None else np.asarray(phase_rad)
    if phases.shape!=out.shape or not np.all(np.isfinite(phases)):raise ValueError('TX LO phase history')
    return output_envelope(out,np.exp(1j*phases),**output_parameters)


class TrainedBlockEqualizer:
    """External FPGA observer: fixed-timing CP blocks, independently known training.

    Generic one-tap frequency-domain least-squares estimate. No payload labels,
    packet acquisition, carrier recovery or fitted payload correction. Training
    must illuminate every requested bin; deep fades are rejected, not inverted.
    """
    def __init__(self,fft_size,cp_samples,bins,min_gain=.001):
        self.fft_size=int(fft_size);self.cp_samples=int(cp_samples)
        self.bins=np.asarray(bins,int).copy()
        if (self.fft_size<2 or not 0<=self.cp_samples<=self.fft_size or
                self.bins.ndim!=1 or not len(self.bins) or
                len(np.unique(self.bins))!=len(self.bins) or
                np.any((self.bins<0)|(self.bins>=self.fft_size)) or
                not math.isfinite(min_gain) or min_gain<=0):
            raise ValueError('Invalid block equalizer geometry')
        self.min_gain=min_gain;self.response=None

    def spectrum(self,samples):
        z=np.asarray(samples,complex)
        if (z.ndim!=1 or not len(z) or len(z)%(self.fft_size+self.cp_samples) or
                not np.all(np.isfinite(z))):
            raise ValueError('Finite complete blocks required')
        blocks=z.reshape(-1,self.fft_size+self.cp_samples)
        return np.fft.fft(blocks[:,self.cp_samples:],axis=1)[:,self.bins]

    def train(self,known_training,received_training):
        # Invalid/rejected retraining must not leave an old estimate usable.
        self.response=None
        x=self.spectrum(known_training);y=self.spectrum(received_training)
        if x.shape!=y.shape:raise ValueError('Training block count mismatch')
        energy=np.sum(abs(x)**2,axis=0)
        if np.any(energy<1e-12):raise ValueError('Training leaves unobserved bins')
        response=np.sum(x.conj()*y,axis=0)/energy
        if np.any(abs(response)<self.min_gain):raise ValueError('Unusable channel estimate')
        self.response=response
        self.response.flags.writeable=False

    def observe(self,received_payload):
        if self.response is None:raise ValueError('Train receiver before observation')
        return self.spectrum(received_payload)/self.response


def repeated_training_frequency(samples,lag,sample_hz,min_coherence=.8):
    """FPGA fine-CFO estimate from two repeated received training intervals.

    Timing and repetition length are supplied by framing. Unambiguous only for
    |CFO| < sample_hz/(2*lag); this is not a coarse acquisition search. No clean
    waveform or transmitted data are available to this estimator.
    """
    z=np.asarray(samples,complex)
    if (not isinstance(lag,(int,np.integer)) or lag<1 or z.shape!=(2*lag,) or
            not np.all(np.isfinite(z)) or not math.isfinite(sample_hz) or sample_hz<=0 or
            not 0<min_coherence<=1):
        raise ValueError('Invalid repeated training')
    a,b=z[:lag],z[lag:]
    power=math.sqrt(float(np.vdot(a,a).real*np.vdot(b,b).real))
    if power<1e-20:raise ValueError('Missing training energy')
    correlation=np.vdot(a,b)
    coherence=float(abs(correlation)/power)
    if coherence<min_coherence:raise ValueError('Incoherent repeated training')
    return float(np.angle(correlation)*sample_hz/(2*math.pi*lag)),coherence
