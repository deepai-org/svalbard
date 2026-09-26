"""Coded HE20 DATA control for the shared RF chain, not an HE packet receiver.

The default control has a known start. --acquisition adds actual legacy training
with unknown arrival/CFO; two known DATA symbols still stand in for HE-LTF. The coding control
uses a terminated rate-1/2, K=7 (133,171 octal) convolutional code and a 26-column
BPSK interleaver. No HE signaling, scrambling, pilot polarity, AGC or MAC claim.
FPGA-side decoding receives samples and a fixed training definition, not payload.
"""
import json
import math
from pathlib import Path
from unittest.mock import patch
import zlib
import numpy as np
import baseline_envelope as b
import selected_rf as rf
from protocol_signals import he20

P=Path(__file__).resolve().parents[1]
POLYNOMIALS=(0o133,0o171)
TRAINING=np.random.default_rng(842).integers(0,2,468)
PERMUTATION=9*(np.arange(234)%26)+np.arange(234)//26


def encode(bits):
    bits=np.asarray(bits)
    if bits.ndim!=1 or np.any((bits!=0)&(bits!=1)):raise ValueError('Binary vector required')
    state=0;out=[]
    for bit in bits:
        register=(int(bit)<<6)|state
        out.extend((register&g).bit_count()%2 for g in POLYNOMIALS)
        state=register>>1
    return np.array(out,dtype=np.uint8)


def decode(soft):
    """Full-record soft Viterbi, zero initial/final state; positive means bit 1."""
    soft=np.asarray(soft,float)
    if soft.ndim!=1 or len(soft)%2 or not np.all(np.isfinite(soft)):raise ValueError('Finite paired soft values required')
    states=np.arange(64);bit=states>>5
    predecessors=np.stack(((states&31)<<1,((states&31)<<1)|1))
    registers=(bit[None,:]<<6)|predecessors
    labels=np.array([[[(int(v)&g).bit_count()%2 for g in POLYNOMIALS] for v in row] for row in registers])
    labels=2*labels-1
    metrics=np.full(64,np.inf);metrics[0]=0.;history=[]
    for pair in soft.reshape(-1,2):
        costs=metrics[predecessors]+np.sum((pair[None,None,:]-labels)**2,axis=-1)
        choice=np.argmin(costs,axis=0)
        metrics=costs[choice,states];metrics-=min(metrics)
        history.append(predecessors[choice,states])
    state=0;bits=[]
    for previous in reversed(history):
        bits.append(state>>5);state=int(previous[state])
    if state!=0:raise ValueError('No path from the declared initial state')
    return np.array(bits[::-1],dtype=np.uint8)


def source(seed):
    payload=np.random.default_rng(seed).integers(0,256,128,dtype=np.uint8).tobytes()
    framed=payload+zlib.crc32(payload).to_bytes(4,'little')
    bits=np.unpackbits(np.frombuffer(framed,dtype=np.uint8),bitorder='little')
    # Ten DATA symbols = 2340 coded bits. Zero padding precedes six tail bits.
    uncoded=np.r_[bits,np.zeros(1170-len(bits),dtype=np.uint8)]
    coded=encode(uncoded).reshape(10,234)
    interleaved=np.empty_like(coded);interleaved[:,PERMUTATION]=coded
    return he20(np.r_[TRAINING,interleaved.ravel()]),payload,interleaved


def waveform_source(wave,oversample):
    cp=wave.metadata['cp'];frames=np.asarray(wave.samples).reshape(-1,256+cp)
    spectrum=np.fft.fft(frames[:,cp:],axis=1)
    padded=np.zeros((len(frames),256*oversample),complex)
    padded[:,:128]=spectrum[:,:128];padded[:,-128:]=spectrum[:,-128:]
    high=np.fft.ifft(padded,axis=1)*oversample
    return wave,np.concatenate([np.r_[row[-cp*oversample:],row] for row in high])


def receive(samples):
    """Fixed geometry and known prefix; no source DATA or actual channel input."""
    training=he20(TRAINING);meta=training.metadata;cp=meta['cp'];n=256+cp
    frames=np.asarray(samples).reshape(12,n)
    known=np.fft.fft(np.asarray(training.samples).reshape(2,n)[:,cp:],axis=1)
    observed=np.fft.fft(frames[:,cp:],axis=1)
    data=np.array(meta['data'])%256;pilots=np.array(meta['pilots'])%256
    occupied=np.r_[data,pilots]
    h=np.zeros(256,complex)
    h[occupied]=np.sum(known[:,occupied].conj()*observed[:2,occupied],axis=0)/np.sum(abs(known[:,occupied])**2,axis=0)
    if np.any(abs(h[occupied])<1e-15):return dict(status='training_unobservable'),None
    equalized=observed[2:,data]/h[data]
    phase=np.angle(np.sum(observed[2:,pilots]/h[pilots],axis=1))
    normalized=equalized*np.exp(-1j*phase[:,None])/(256/math.sqrt(242))
    # Fixed unweighted Euclidean metric; no true channel/noise or decoded-data
    # feedback adjusts the receiver. Frequency-dependent reliability is future work.
    recovered=decode(normalized.real[:,PERMUTATION].ravel())
    octets=np.packbits(recovered[:1056],bitorder='little').tobytes()
    crc_ok=zlib.crc32(octets[:128])==int.from_bytes(octets[128:132],'little')
    return dict(status='decoded',crc_ok=crc_ok,tail_zero=bool(np.all(recovered[-6:]==0)),
        payload_hex=octets[:128].hex(),soft_metric='unweighted Euclidean',
        known_data_training_symbols=2,real_preamble_acquisition=False),normalized.real>0


def run_case(environment,seed):
    wave,payload,transmitted=source(seed)
    capture={}
    original=rf.wideband_receive
    def observed(*args,**kwargs):
        kwargs['observation_capture']=capture
        return original(*args,**kwargs)
    with patch.object(rf,'he_source',side_effect=lambda **kw:waveform_source(wave,kw['oversample'])),patch.object(b,'wideband_receive',side_effect=observed):
        analog=b.coupled_wideband_feedback(environment,wanted_dbm=-85.,gain_db=54.,oversample=256)
    rx,decisions=receive(capture['observed'])
    return dict(seed=seed,analog=analog,receiver=rx,
        raw_bit_errors=None if decisions is None else int(np.sum(decisions!=transmitted)),
        payload_correct=rx.get('payload_hex')==payload.hex(),
        scope='Coded DATA attribution only. Fixed known DATA training, ideal boundaries and fixed gain remain; no HE preamble/header, standard scrambling/pilot sequence, acquisition, MAC timing or packet/PER qualification.')


def legacy_preamble(oversample=1):
    """20 MHz L-STF and L-LTF tone definitions, unit mean symbol power.

    Field lengths follow IEEE legacy training, common to HE packets. The
    surrounding coded-DATA fixture is NOT a valid HE PPDU. No TX windowing.
    """
    short=np.zeros(64,complex);long=np.zeros(64,complex)
    short[np.array([-24,-20,-16,-12,-8,-4,4,8,12,16,20,24])%64]=(1+1j)*math.sqrt(13/6)*np.array([1,-1,1,-1,-1,1,-1,-1,1,1,1,1])
    long[np.arange(-26,27)%64]=[1,1,-1,-1,1,1,-1,1,-1,1,1,1,1,1,1,-1,-1,1,1,-1,1,-1,1,1,1,1,0,
        1,-1,-1,1,1,-1,1,-1,1,-1,-1,-1,-1,-1,1,1,-1,-1,1,-1,1,-1,1,1,1,1]
    def symbol(bins):
        high=np.zeros(64*oversample,complex)
        high[:32]=bins[:32];high[-32:]=bins[-32:]
        return np.fft.ifft(high)*64*oversample/math.sqrt(52)
    stf=symbol(short)[:16*oversample];ltf=symbol(long)
    return np.r_[np.tile(stf,10),ltf[-32*oversample:],ltf,ltf],ltf


def acquisition_source(wave,oversample,start_sample,carrier_offset_hz,transmit=True):
    from dataclasses import replace
    preamble,_=legacy_preamble(oversample)
    _,data=waveform_source(wave,oversample)
    high=np.r_[np.zeros(start_sample*oversample),preamble,data,np.zeros(128*oversample)]
    high*=np.exp(2j*np.pi*carrier_offset_hz*np.arange(len(high))/(20e6*oversample)+.37j)
    if not transmit:high[:]=0.
    # The observer receives the entire capture, including noise before arrival.
    observed_wave=replace(wave,samples=high[::oversample].copy())
    return observed_wave,high


def acquire(samples,*,coarse_threshold=.25):
    """Detect repeated STF, then paired LTF correlations; no arrival/CFO truth.

    Fixed thresholds/search windows, no CRC-aided selection. A 0.25 squared
    coherence threshold corresponds to 0 dB SNR in the ideal independent-noise
    approximation; the LTF match supplies the second rejection stage. This is
    a receiver design setting, not a protocol mask or a measured sensitivity.
    Search may buffer samples beyond L-LTF; decision_sample records that cost.
    """
    samples=np.asarray(samples,complex);lag=16;window=64
    if samples.ndim!=1 or len(samples)<480 or not np.all(np.isfinite(samples)):
        raise ValueError('Finite continuous 20 MHz capture required')
    def moving(values):
        sums=np.r_[0,np.cumsum(values)]
        return sums[window:]-sums[:-window]
    correlation=moving(samples[:-lag].conj()*samples[lag:])
    first=moving(abs(samples[:-lag])**2);second=moving(abs(samples[lag:])**2)
    metric=abs(correlation)**2/np.maximum(first*second,1e-30)
    plateau=np.convolve((metric>coarse_threshold).astype(int),np.ones(32,dtype=int),'valid')==32
    starts=[];next_search=0
    for candidate in np.flatnonzero(plateau):
        if candidate>=next_search:
            starts.append(candidate);next_search=candidate+64
    _,template=legacy_preamble();energy=float(np.vdot(template,template).real)
    for start in starts:
        ready=int(start+window+lag+31)
        coarse=float(np.angle(sum(correlation[start:start+32]))*20e6/(2*np.pi*lag))
        if abs(coarse)>250e3:continue
        corrected=samples*np.exp(-2j*np.pi*coarse*np.arange(len(samples))/20e6)
        candidates=np.arange(ready,min(ready+192,len(samples)-128))
        if not len(candidates):continue
        matches=np.correlate(corrected,template,'valid')
        levels=moving(abs(corrected)**2)
        scores=abs(matches)**2/np.maximum(energy*levels,1e-30)
        paired=np.minimum(scores[candidates],scores[candidates+64])
        best=int(np.argmax(paired));n=int(candidates[best])
        if paired[best]<.3:continue
        fine=float(np.angle(np.vdot(corrected[n:n+64],corrected[n+64:n+128]))*20e6/(2*np.pi*64))
        offset=coarse+fine
        corrected=samples*np.exp(-2j*np.pi*offset*np.arange(len(samples))/20e6)
        return dict(status='legacy_training_acquired',data_start_sample=n+128,
            decision_sample=int(candidates[-1]+128),coarse_cfo_hz=coarse,
            estimated_cfo_hz=offset,ltf_score=float(paired[best]),
            legacy_training_acquired=True,he_packet_acquired=False,coarse_metric_threshold=coarse_threshold),corrected
    return dict(status='preamble_not_acquired',legacy_training_acquired=False,he_packet_acquired=False,coarse_metric_threshold=coarse_threshold),None


def run_acquisition_case(environment,seed,*,start_sample,carrier_offset_hz,transmit=True,oversample=256):
    wave,payload,transmitted=source(seed);capture={};original=rf.wideband_receive
    def observed(*args,**kwargs):
        kwargs['observation_capture']=capture
        return original(*args,**kwargs)
    with patch.object(rf,'he_source',side_effect=lambda **kw:acquisition_source(wave,kw['oversample'],start_sample,carrier_offset_hz,transmit)),\
         patch.object(rf,'he_observation',return_value=dict(scope='Continuous capture delivered to external acquisition receiver; no oracle DATA alignment.')),\
         patch.object(b,'wideband_receive',side_effect=observed):
        analog=b.coupled_wideband_feedback(environment,wanted_dbm=-85.,gain_db=54.,oversample=oversample)
    acquisition,corrected=acquire(capture['observed']);rx={};decisions=None
    strict,_=acquire(capture['observed'],coarse_threshold=.6)
    if corrected is not None:
        start=acquisition['data_start_sample'];end=start+len(wave.samples)
        if end<=len(corrected):rx,decisions=receive(corrected[start:end])
        else:rx=dict(status='capture_ended_before_data')
    return dict(seed=seed,source_start_sample=start_sample,source_carrier_offset_hz=carrier_offset_hz,transmitted=transmit,
        analog=analog,acquisition=acquisition,strict_coarse_control=strict,receiver=rx,
        estimated_data_start_error_samples=None if corrected is None else acquisition['data_start_sample']-(start_sample+320),
        raw_bit_errors=None if decisions is None else int(np.sum(decisions!=transmitted)),
        payload_correct=bool(transmit and rx.get('payload_hex')==payload.hex()),
        scope='Actual legacy training sequences precede diagnostic coded HE20 DATA. Arrival and CFO are unknown to the receiver; fixed gain, known DATA training and fixed geometry remain. No HE signaling/HE-LTF, scrambling/pilot sequence, AGC, sample-rate ppm, packet timing or PER qualification.')


if __name__=='__main__':
    import argparse
    import hashlib
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--acquisition',action='store_true')
    args=parser.parse_args()
    contract=json.loads((P/'spec/contract.json').read_text());rows=[]
    for carrier in (2.4e9,2.484e9):
        original=b.selected_environment(contract,'rf',carrier,carrier/16)
        for peak in (.5,.75):
            environment,clock=b.reference_payload_environment(original,dict(link_r_ohm=1e-5),False,source_peak_v=peak)
            for index,seed in enumerate((431,719,9021)):
                result=(run_acquisition_case(environment,seed,start_sample=(137,411,73)[index],carrier_offset_hz=(-120e3,0.,120e3)[index])
                    if args.acquisition else run_case(environment,seed))
                rows.append(dict(carrier_hz=carrier,source_peak_v=peak,clock=clock,result=result))
                print(carrier,peak,seed,result.get('acquisition',{}).get('status'),result['raw_bit_errors'],result['receiver'].get('crc_ok'),result['payload_correct'],flush=True)
    if args.acquisition:
        result=run_acquisition_case(environment,431,start_sample=137,carrier_offset_hz=0.,transmit=False)
        rows.append(dict(carrier_hz=carrier,source_peak_v=peak,clock=clock,result=result))
    baseline=json.loads((P/'evidence/selected-baseline.json').read_text())
    sources=set(baseline['sources_sha256'])|{'verification/wideband_packet.py'}
    report=dict(cases=rows,scope='Selected single-ended architecture, current 0.25 nH package target, 236 mA RF budget, positive assigned supply-delay sign; weak -85 dBm wanted and -30 dBm CW blocker at +12 MHz. Three payload seeds at two LO endpoints and two source drives. Coded DATA control, not a valid Wi-Fi packet. Acquisition mode adds real legacy training with unknown arrival/CFO and a no-wanted-signal control; HE-specific fields remain absent.',
        sources_sha256={name:hashlib.sha256((P/name).read_bytes()).hexdigest() for name in sorted(sources)})
    name='wideband-acquisition-control.json' if args.acquisition else 'wideband-coded-control.json'
    (P/'evidence'/name).write_text(json.dumps(report,indent=2,default=lambda x:x.item())+'\n')
