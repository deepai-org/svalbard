"""Coded HE20 DATA control for the shared RF chain, not an HE packet receiver.

The default control has a known start. --acquisition adds actual legacy training
with unknown arrival/CFO; two known DATA symbols still stand in for HE-LTF. The coding control
uses a terminated rate-1/2, K=7 (133,171 octal) convolutional code and a 26-column
BPSK interleaver and explicit seeded DATA/padding whitening. No HE signaling,
standard scrambling, pilot polarity, AGC or MAC claim.
FPGA-side decoding receives samples and a fixed training definition, not payload.
"""
import json
import hashlib
from copy import deepcopy
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


def coded_data_geometry(payload_bytes):
    if type(payload_bytes) is not int or not 1<=payload_bytes<=65531:
        raise ValueError('Diagnostic payload length must be 1..65531 bytes')
    framed_bits=8*(payload_bytes+4)
    data_symbols=max(10,math.ceil((framed_bits+6)/117))
    return dict(payload_bytes=payload_bytes,framed_bytes=payload_bytes+4,
        framed_bits=framed_bits,data_symbols=data_symbols,total_symbols=data_symbols+2,
        uncoded_bits=data_symbols*117)


def whitening_mask(length,seed):
    """Known fixture mask; whiten padding but retain six zero BCC tail bits.

    This is deliberately not presented as standards-compliant scrambling or
    autonomous seed recovery. None preserves the unwhitened overload control.
    """
    if seed is None:return np.zeros(length,np.uint8)
    if type(seed) is not int or seed<0:raise ValueError('Nonnegative whitening seed required')
    return np.r_[np.random.default_rng(seed).integers(0,2,length-6,dtype=np.uint8),np.zeros(6,np.uint8)]


def source(seed,*,payload_bytes=128,packet=None,whitening_seed=91):
    geometry=coded_data_geometry(payload_bytes)
    if packet is not None and (not isinstance(packet,bytes) or len(packet)!=payload_bytes):
        raise ValueError('Packet must be bytes matching the declared payload length')
    payload=(np.random.default_rng(seed).integers(0,256,payload_bytes,dtype=np.uint8).tobytes()
             if packet is None else packet)
    framed=payload+zlib.crc32(payload).to_bytes(4,'little')
    bits=np.unpackbits(np.frombuffer(framed,dtype=np.uint8),bitorder='little')
    # Retain legacy minimum geometry; padding includes at least six tail bits.
    uncoded=np.r_[bits,np.zeros(geometry['uncoded_bits']-len(bits),dtype=np.uint8)]
    coded=encode(uncoded^whitening_mask(len(uncoded),whitening_seed)).reshape(geometry['data_symbols'],234)
    interleaved=np.empty_like(coded);interleaved[:,PERMUTATION]=coded
    return he20(np.r_[TRAINING,interleaved.ravel()]),payload,interleaved


def waveform_source(wave,oversample):
    cp=wave.metadata['cp'];frames=np.asarray(wave.samples).reshape(-1,256+cp)
    spectrum=np.fft.fft(frames[:,cp:],axis=1)
    padded=np.zeros((len(frames),256*oversample),complex)
    padded[:,:128]=spectrum[:,:128];padded[:,-128:]=spectrum[:,-128:]
    high=np.fft.ifft(padded,axis=1)*oversample
    return wave,np.concatenate([np.r_[row[-cp*oversample:],row] for row in high])


def receive(samples,*,payload_bytes=128,whitening_seed=91):
    """Configured length and known prefix; no source DATA or actual channel input."""
    geometry=coded_data_geometry(payload_bytes)
    training=he20(TRAINING);meta=training.metadata;cp=meta['cp'];n=256+cp
    frames=np.asarray(samples).reshape(geometry['total_symbols'],n)
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
    recovered^=whitening_mask(len(recovered),whitening_seed)
    octets=np.packbits(recovered[:geometry['framed_bits']],bitorder='little').tobytes()
    crc_ok=zlib.crc32(octets[:payload_bytes])==int.from_bytes(octets[payload_bytes:payload_bytes+4],'little')
    return dict(status='decoded',crc_ok=crc_ok,tail_zero=bool(np.all(recovered[-6:]==0)),
        payload_hex=octets[:payload_bytes].hex(),geometry=geometry,soft_metric='unweighted Euclidean',
        known_data_training_symbols=2,real_preamble_acquisition=False),normalized.real>0


def packet_context(environment, payload, *, seed, wanted_dbm, blocker_dbm):
    """Detached input record; independent waveform fixtures have no chip identity."""
    context=deepcopy({key:environment[key] for key in (
        'design_provenance','resolved_configuration','scenario_overrides',
        'scenario_assumptions','operating_conditions') if key in environment})
    context['packet_stimuli']=dict(seed=seed,payload_bytes=len(payload),
        payload_sha256=hashlib.sha256(payload).hexdigest(),
        wanted_dbm=wanted_dbm,blocker_dbm=blocker_dbm,diagnostic_whitening_seed=91,
        waveform_scope='Seeded DATA/padding whitening; not WLAN scrambler or HE PPDU')
    return context


def run_case(environment,seed,*,payload_bytes=128,packet=None,wanted_dbm=-85.,blocker_dbm=-30.):
    rf.validate_rf_configuration_identity(environment)
    wave,payload,transmitted=source(seed,payload_bytes=payload_bytes,packet=packet)
    context=packet_context(environment,payload,seed=seed,wanted_dbm=wanted_dbm,blocker_dbm=blocker_dbm)
    capture={}
    original=rf.wideband_receive
    def observed(*args,**kwargs):
        kwargs['observation_capture']=capture
        return original(*args,**kwargs)
    with patch.object(rf,'he_source',side_effect=lambda **kw:waveform_source(wave,kw['oversample'])),patch.object(b,'wideband_receive',side_effect=observed):
        analog=b.coupled_wideband_feedback(environment,wanted_dbm=wanted_dbm,blocker_dbm=blocker_dbm,gain_db=(environment['resolved_configuration']['pga_gain_db'] if 'resolved_configuration' in environment
            else b.receiver_inventory_options(environment)['maximum_gain_db']))
    rx,decisions=receive(capture['observed'],payload_bytes=payload_bytes)
    return dict(**context,seed=seed,analog=analog,receiver=rx,
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


def acquisition_source(wave,oversample,start_sample,carrier_offset_hz,transmit=True,*,tail_samples=128):
    from dataclasses import replace
    preamble,_=legacy_preamble(oversample)
    _,data=waveform_source(wave,oversample)
    if type(tail_samples) is not int or tail_samples<0:raise ValueError("Capture tail")
    high=np.r_[np.zeros(start_sample*oversample),preamble,data,np.zeros(tail_samples*oversample)]
    high*=np.exp(2j*np.pi*carrier_offset_hz*np.arange(len(high))/(20e6*oversample)+.37j)
    if not transmit:high[:]=0.
    # The observer receives the entire capture, including noise before arrival.
    observed_wave=replace(wave,samples=high[::oversample].copy())
    return observed_wave,high


def acquire(samples,*,coarse_threshold=.25,valid=None,coarse_window=64,coarse_plateau=32):
    """Detect repeated STF, then paired LTF correlations; no arrival/CFO truth.

    Fixed thresholds/search windows, no CRC-aided selection. A 0.25 squared
    coherence threshold corresponds to 0 dB SNR in the ideal independent-noise
    approximation; the LTF match supplies the second rejection stage. This is
    a receiver design setting, not a protocol mask or a measured sensitivity.
    Shorter coarse support permits reacquisition around a marked PGA gap;
    the two complete 64-sample LTF checks are unchanged.
    Search may buffer samples beyond L-LTF; decision_sample records that cost.
    """
    samples=np.asarray(samples,complex);lag=16;window=coarse_window
    if type(window) is not int or window<16 or type(coarse_plateau) is not int or coarse_plateau<1:
        raise ValueError("Acquisition correlation support")
    if samples.ndim!=1 or len(samples)<480 or not np.all(np.isfinite(samples)):
        raise ValueError('Finite continuous 20 MHz capture required')
    valid=np.ones(len(samples),bool) if valid is None else np.asarray(valid,bool)
    if valid.shape!=samples.shape:raise ValueError('Capture validity shape')
    invalid_prefix=np.r_[0,np.cumsum(~valid)]
    def clean(starts,length):
        return invalid_prefix[starts+length]==invalid_prefix[starts]
    def moving(values):
        sums=np.r_[0,np.cumsum(values)]
        return sums[window:]-sums[:-window]
    correlation=moving(samples[:-lag].conj()*samples[lag:])
    first=moving(abs(samples[:-lag])**2);second=moving(abs(samples[lag:])**2)
    metric=abs(correlation)**2/np.maximum(first*second,1e-30)
    metric[~clean(np.arange(len(metric)),window+lag)]=0.
    plateau=np.convolve((metric>coarse_threshold).astype(int),np.ones(coarse_plateau,dtype=int),'valid')==coarse_plateau
    starts=[];next_search=0
    for candidate in np.flatnonzero(plateau):
        if candidate>=next_search:
            starts.append(candidate);next_search=candidate+64
    _,template=legacy_preamble();energy=float(np.vdot(template,template).real)
    for start in starts:
        ready=int(start+window+lag+coarse_plateau-1)
        coarse=float(np.angle(sum(correlation[start:start+coarse_plateau]))*20e6/(2*np.pi*lag))
        if abs(coarse)>250e3:continue
        corrected=samples*np.exp(-2j*np.pi*coarse*np.arange(len(samples))/20e6)
        candidates=np.arange(ready,min(ready+192,len(samples)-128))
        if not len(candidates):continue
        search_end=int(candidates[-1]+128)
        candidates=candidates[clean(candidates,128)]
        if not len(candidates):continue
        matches=np.correlate(corrected,template,'valid')
        power_prefix=np.r_[0,np.cumsum(abs(corrected)**2)]
        levels=power_prefix[64:]-power_prefix[:-64]
        scores=abs(matches)**2/np.maximum(energy*levels,1e-30)
        paired=np.minimum(scores[candidates],scores[candidates+64])
        best=int(np.argmax(paired));n=int(candidates[best])
        if paired[best]<.3:continue
        fine=float(np.angle(np.vdot(corrected[n:n+64],corrected[n+64:n+128]))*20e6/(2*np.pi*64))
        offset=coarse+fine
        corrected=samples*np.exp(-2j*np.pi*offset*np.arange(len(samples))/20e6)
        return dict(status='legacy_training_acquired',data_start_sample=n+128,
            coarse_start_sample=int(start),ltf_start_sample=n,
            decision_sample=search_end,coarse_cfo_hz=coarse,
            estimated_cfo_hz=offset,ltf_score=float(paired[best]),
            legacy_training_acquired=True,he_packet_acquired=False,coarse_metric_threshold=coarse_threshold),corrected
    return dict(status='preamble_not_acquired',legacy_training_acquired=False,he_packet_acquired=False,coarse_metric_threshold=coarse_threshold),None


def run_acquisition_case(environment,seed,*,start_sample,carrier_offset_hz,transmit=True,oversample=None,payload_bytes=128,
                         wanted_dbm=-85.,gain_db=None,sar_parameters=None,comparator_model=None,gain_codes_db=None,
                              blocker_dbm=-30.,noise_figure_db=None,input_iip3_dbm=None,
                              gain_initial_db=None,gain_tau_s=None,gain_command_s=0.,gain_hypothesis_reason=None):
    rf.validate_rf_configuration_identity(environment)
    if gain_db is None:gain_db=(environment['resolved_configuration']['pga_gain_db'] if 'resolved_configuration' in environment
            else b.receiver_inventory_options(environment)['maximum_gain_db'])
    wave,payload,transmitted=source(seed,payload_bytes=payload_bytes);capture={};original=rf.wideband_receive
    context=packet_context(environment,payload,seed=seed,wanted_dbm=wanted_dbm,blocker_dbm=blocker_dbm)
    def observed(*args,**kwargs):
        kwargs['observation_capture']=capture
        return original(*args,**kwargs)
    with patch.object(rf,'he_source',side_effect=lambda **kw:acquisition_source(wave,kw['oversample'],start_sample,carrier_offset_hz,transmit)),\
         patch.object(rf,'he_observation',return_value=dict(scope='Continuous capture delivered to external acquisition receiver; no oracle DATA alignment.')),\
         patch.object(b,'wideband_receive',side_effect=observed):
        analog=b.coupled_wideband_feedback(environment,wanted_dbm=wanted_dbm,gain_db=gain_db,oversample=oversample,
            sar_parameters=sar_parameters,comparator_model=comparator_model,gain_codes_db=gain_codes_db,
            blocker_dbm=blocker_dbm,noise_figure_db=noise_figure_db,input_iip3_dbm=input_iip3_dbm,
            gain_initial_db=gain_initial_db,gain_tau_s=gain_tau_s,gain_command_s=gain_command_s,
            gain_hypothesis_reason=gain_hypothesis_reason)
    acquisition,corrected=acquire(capture['observed']);rx={};decisions=None
    strict,_=acquire(capture['observed'],coarse_threshold=.6)
    if corrected is not None:
        start=acquisition['data_start_sample'];end=start+len(wave.samples)
        if end<=len(corrected):rx,decisions=receive(corrected[start:end],payload_bytes=payload_bytes)
        else:rx=dict(status='capture_ended_before_data')
    return dict(**context,seed=seed,source_start_sample=start_sample,source_carrier_offset_hz=carrier_offset_hz,transmitted=transmit,
        analog=analog,acquisition=acquisition,strict_coarse_control=strict,receiver=rx,
        estimated_data_start_error_samples=None if corrected is None else acquisition['data_start_sample']-(start_sample+320),
        raw_bit_errors=None if decisions is None else int(np.sum(decisions!=transmitted)),
        payload_correct=bool(transmit and rx.get('payload_hex')==payload.hex()),
        scope='Actual legacy training sequences precede diagnostic coded HE20 DATA. Arrival and CFO are unknown to the receiver; fixed gain, known DATA training and fixed geometry remain. No HE signaling/HE-LTF, scrambling/pilot sequence, AGC, sample-rate ppm, packet timing or PER qualification.')


def main(argv=None):
    import argparse
    import hashlib
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--acquisition',action='store_true')
    args=parser.parse_args(argv)
    from reference_input_probe import probe_source_hashes
    hashes=probe_source_hashes()
    from design_definition import load_design
    design=load_design();rows=[]
    for carrier in (2.4e9,2.484e9):
        config=design.configure(engine='rf',direction='rx',reference_hz=carrier,
            sample_divider=64,pga_gain_db=max(design.architecture['blocks']['pga_i']['parameters']['gain_db']))
        original=b.configured_environment(config)
        for peak in (.5,.75):
            environment,clock=b.reference_payload_environment(original,dict(link_r_ohm=1e-5),False,source_peak_v=peak)
            if environment is None:
                rows.append(dict(resolved_configuration=config.record(),scenario_overrides=original['scenario_overrides'],
                                 carrier_hz=carrier,source_peak_v=peak,clock=clock,
                                 status='clock_rejected',result=None))
                continue
            for index,seed in enumerate((431,719,9021)):
                result=(run_acquisition_case(environment,seed,start_sample=(137,411,73)[index],carrier_offset_hz=(-120e3,0.,120e3)[index])
                    if args.acquisition else run_case(environment,seed))
                rows.append(dict(resolved_configuration=config.record(),scenario_overrides=original['scenario_overrides'],
                                 carrier_hz=carrier,source_peak_v=peak,clock=clock,result=result))
                print(carrier,peak,seed,result.get('acquisition',{}).get('status'),result['raw_bit_errors'],result['receiver'].get('crc_ok'),result['payload_correct'],flush=True)
    if args.acquisition and environment is not None:
        result=run_acquisition_case(environment,431,start_sample=137,carrier_offset_hz=0.,transmit=False)
        rows.append(dict(resolved_configuration=config.record(),scenario_overrides=original['scenario_overrides'],
                                 carrier_hz=carrier,source_peak_v=peak,clock=clock,result=result))
    if any(hashlib.sha256((P/name).read_bytes()).hexdigest()!=value for name,value in hashes.items()):
        raise RuntimeError('Sources changed during wideband campaign')
    report=dict(design_provenance=design.provenance(),cases=rows,scope='Differential reference input with explicit source-amplitude controls, current package target and RF receive allocation, positive assigned supply-delay sign; weak -85 dBm wanted and -30 dBm CW blocker at +12 MHz. Three payload seeds at two LO endpoints and two source drives. Coded DATA control, not a valid Wi-Fi packet. Acquisition mode adds real legacy training with unknown arrival/CFO and a no-wanted-signal control; HE-specific fields remain absent.',
        sources_sha256=hashes)
    name='wideband-acquisition-control.json' if args.acquisition else 'wideband-coded-control.json'
    b.write_evidence(P/'evidence'/name,json.loads(json.dumps(report,default=lambda x:x.item())))
    return report


if __name__=='__main__':
    main()
