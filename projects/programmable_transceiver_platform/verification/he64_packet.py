"""MCS0..7 HE-tone DATA stress record, not a standard HE PPDU.

Default MCS7 preserves the existing 64-QAM rate5/6 control. Known DATA
training, configured length, constant pilots remain
fixture aids; no HE signaling, standard scrambling, RU mapping or router claim.
Optional seeded whitening is a DATA crest control, not a WLAN scrambler.
"""
import math
import zlib
import numpy as np
from wideband_packet import encode,decode,TRAINING,whitening_mask
from protocol_signals import he20,Waveform

# MCS0..7: bits/subcarrier, code-rate numerator/denominator.
MCS=((1,1,2),(2,1,2),(2,3,4),(4,1,2),(4,3,4),(6,2,3),(6,3,4),(6,5,6))
MASKS={(1,2):[1,1],(2,3):[1,1,1,0],(3,4):[1,1,1,0,0,1],
       (5,6):[1,1,1,0,0,1,1,0,0,1]}

def constellation(bits):
    v=1-2*np.asarray(bits,int);n=v.shape[-1]
    if n==1:return v[...,0].astype(complex)
    if n==2:return (v[...,0]+1j*v[...,1])/math.sqrt(2)
    if n==4:return (v[...,0]*(2-v[...,2])+1j*v[...,1]*(2-v[...,3]))/math.sqrt(10)
    if n==6:return (v[...,0]*(4-v[...,2]*(2-v[...,4]))+1j*v[...,1]*(4-v[...,3]*(2-v[...,5])))/math.sqrt(42)
    raise ValueError('Unsupported constellation')

def parameters(mcs):
    if type(mcs) is not int or not 0<=mcs<=7:raise ValueError('MCS must be0..7')
    n,num,den=MCS[mcs];cbps=234*n;k=np.arange(cbps);i=9*n*(k%26)+k//26;s=max(n//2,1)
    permutation=s*(i//s)+(i+cbps-(26*i)//cbps)%s
    labels=(np.arange(2**n)[:,None]>>np.arange(n))&1
    return n,234*n*num//den,np.asarray(MASKS[num,den],bool),permutation,labels,constellation(labels)

# Compatibility names for the default MCS7 diagnostic and reference comparison.
_,_,PUNCTURE,INTERLEAVER,LABEL_BITS,POINTS=parameters(7)


def geometry(payload_bytes,mcs=7):
    if type(payload_bytes) is not int or not 1<=payload_bytes<=65531:raise ValueError('Length')
    _,dbps,*_=parameters(mcs)
    symbols=math.ceil((8*(payload_bytes+4)+6)/dbps)
    return symbols,symbols*dbps




def source(payload,*,mcs=7,whitening_seed=None):
    if not isinstance(payload,bytes):raise ValueError('Payload bytes')
    symbols,uncoded=geometry(len(payload),mcs)
    n,_,puncture,permutation,_,_=parameters(mcs)
    framed=payload+zlib.crc32(payload).to_bytes(4,'little')
    bits=np.unpackbits(np.frombuffer(framed,dtype=np.uint8),bitorder='little')
    coded=encode(np.r_[bits,np.zeros(uncoded-len(bits),np.uint8)]^whitening_mask(uncoded,whitening_seed))
    punctured=coded[np.resize(puncture,len(coded))]
    interleaved=np.empty((symbols,234*n),np.uint8)
    interleaved[:,permutation]=punctured.reshape(symbols,234*n)
    data_values=constellation(interleaved.reshape(symbols,234,n))
    training=he20(TRAINING);m=training.metadata
    data=np.array(m['data'])%256;pilots=np.array(m['pilots'])%256
    spectrum=np.zeros((symbols,256),complex)
    spectrum[:,data]=data_values;spectrum[:,pilots]=1
    time=np.fft.ifft(spectrum,axis=1)*256/math.sqrt(242)
    samples=np.concatenate([training.samples,*[np.r_[row[-16:],row] for row in time]])
    return Waveform(samples,20e6,'he64_coded_data_control',punctured,m)


def receive(samples,payload_bytes,*,timing_search=False,mcs=7,whitening_seed=None):
    symbols,uncoded=geometry(payload_bytes,mcs)
    n,_,puncture,permutation,labels,points=parameters(mcs)
    samples=np.asarray(samples)
    training=he20(TRAINING);m=training.metadata
    delay=0
    if timing_search:
        # Select an FFT window from known training consistency only; never DATA.
        known=np.fft.fft(training.samples.reshape(2,272)[:,16:],axis=1)
        active=np.r_[m['data'],m['pilots']]%256
        scores=[]
        for shift in range(13):
            candidate=np.r_[np.zeros(shift),samples][:len(samples)].reshape(symbols+2,272)
            observed=np.fft.fft(candidate[:2,16:],axis=1)[:,active]/known[:,active]
            scores.append(float(np.mean(abs(observed[0]-observed[1])**2)/max(np.mean(abs(observed)**2),1e-30)))
        delay=int(np.argmin(scores))
        samples=np.r_[np.zeros(delay),samples][:len(samples)]
    rows=samples.reshape(symbols+2,272)
    x=np.fft.fft(training.samples.reshape(2,272)[:,16:],axis=1)
    y=np.fft.fft(rows[:,16:],axis=1)
    active=np.r_[m['data'],m['pilots']]%256
    data=np.array(m['data'])%256;pilots=np.array(m['pilots'])%256
    h=np.ones(256,complex);h[active]=np.sum(x[:,active].conj()*y[:2,active],axis=0)/np.sum(abs(x[:,active])**2,axis=0)
    if np.any(abs(h[active])<1e-12):raise ValueError('Unobservable training')
    equalized=y[2:,data]/h[data]/(256/math.sqrt(242))
    phase=np.angle(np.sum(y[2:,pilots]/h[pilots],axis=1))
    equalized*=np.exp(-1j*phase[:,None])
    distance=abs(equalized.ravel()[:,None]-points[None,:])**2
    # Max-log soft evidence; erased puncture positions get zero evidence.
    soft=np.empty((distance.shape[0],n))
    for bit in range(n):
        soft[:,bit]=np.min(distance[:,labels[:,bit]==0],axis=1)-np.min(distance[:,labels[:,bit]==1],axis=1)
    expanded=np.zeros(2*uncoded)
    expanded[np.resize(puncture,len(expanded))]=soft.reshape(symbols,234*n)[:,permutation].ravel()
    recovered=decode(expanded)^whitening_mask(uncoded,whitening_seed)
    octets=np.packbits(recovered[:8*(payload_bytes+4)],bitorder='little').tobytes()
    # Diagnostic peer measurement from received pilots, not injected LO truth.
    # Constant-pilot fixture only; a standard HE receiver must track polarity.
    pilot_time=np.arange(symbols)*272/20e6
    pilot_cfo=(float(np.polyfit(pilot_time,np.unwrap(phase),1)[0]/(2*np.pi))
               if symbols>=2 else None)
    tail_count=min(symbols,8)
    tail_cfo=(float(np.polyfit(pilot_time[-tail_count:],np.unwrap(phase)[-tail_count:],1)[0]/(2*np.pi))
              if tail_count>=2 else None)
    return dict(tail_pilot_frequency_offset_hz=tail_cfo,pilot_frequency_offset_hz=pilot_cfo,fft_window_advance_samples=delay,crc_ok=zlib.crc32(octets[:-4])==int.from_bytes(octets[-4:],'little'),
                payload=octets[:-4],equalized=equalized,
                nearest_constellation_evm=float(np.sqrt(np.mean(np.min(distance,axis=1)))))


def reference_evm(result,payload,*,mcs=7,whitening_seed=None):
    """Score against transmitted DATA truth, never feed truth to the receiver.

    Includes training-derived equalization and received-pilot phase correction;
    this is diagnostic receiver EVM, not a standard transmitter EVM measurement.
    Unlike nearest-point error, wrong constellation decisions remain errors.
    """
    wave=source(payload,mcs=mcs,whitening_seed=whitening_seed)
    rows=wave.samples.reshape(-1,272)[2:,16:]
    tones=np.asarray(wave.metadata['data'])%256
    reference=np.fft.fft(rows,axis=1)[:,tones]/(256/math.sqrt(242))
    observed=np.asarray(result['equalized'])
    if observed.shape!=reference.shape:raise ValueError('DATA reference shape mismatch')
    return float(np.sqrt(np.sum(abs(observed-reference)**2)/np.sum(abs(reference)**2)))


def scalar_observer_evm(samples,payload,*,mcs=7,whitening_seed=None):
    """Declared-time DATA observer: one training scalar, no tone/phase tracking.

    Caller supplies band-selected samples at the declared waveform alignment.
    Uncompensated delay and residual carrier error intentionally remain errors.
    Not the standardized HE transmitter measurement procedure.
    """
    wave=source(payload,mcs=mcs,whitening_seed=whitening_seed)
    samples=np.asarray(samples)
    if samples.shape!=wave.samples.shape:raise ValueError('Observer shape mismatch')
    x=np.fft.fft(wave.samples.reshape(-1,272)[:,16:],axis=1)
    y=np.fft.fft(samples.reshape(-1,272)[:,16:],axis=1)
    active=np.r_[wave.metadata['data'],wave.metadata['pilots']]%256
    data=np.asarray(wave.metadata['data'])%256
    gain=np.vdot(x[:2,active],y[:2,active])/np.vdot(x[:2,active],x[:2,active])
    if abs(gain)<1e-12:raise ValueError('Unobservable scalar gain')
    return float(np.sqrt(np.sum(abs(y[2:,data]/gain-x[2:,data])**2)/
                         np.sum(abs(x[2:,data])**2)))
