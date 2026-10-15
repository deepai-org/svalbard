"""Optional independent legacy-waveform cross-check; not HE interoperability.

Run with --reference-tools pointing at cloud9477/gr-ieee80211 tools/ from
commit dc93c8f30de46082690d5768d6ad03ea2c11e2cb (v1.0). Reference code remains
external, under its upstream AGPL-3.0 license; this script vendors no code.
Its Python transmitter requires matplotlib as well as numpy.
"""
import argparse
import json
import sys
import subprocess
import math
import zlib
from pathlib import Path
import numpy as np
from scipy.signal import resample_poly
from wifi_client_exchange import ClientBench
from wideband_packet import acquire,legacy_preamble,decode


def decode_legacy_signal(corrected, start):
    """Decode L-SIG after L-LTF using only received training and fixed OFDM geometry.

    start is the acquired end of L-LTF. Header parity/reserved/tail and recognized
    RATE are checked; a valid header does not prove DATA or MAC validity.
    """
    if start<128 or len(corrected)<start+80:
        raise ValueError('Incomplete L-SIG capture')
    _,ltf=legacy_preamble()
    occupied=np.r_[np.arange(-26,0),np.arange(1,27)]%64
    pilots=np.array([-21,-7,7,21])%64
    data=np.array([k for k in range(-26,27) if k not in (0,-21,-7,7,21)])%64
    known=np.fft.fft(ltf)
    channel=np.ones(64,complex)
    observed=(np.fft.fft(corrected[start-128:start-64])+np.fft.fft(corrected[start-64:start]))/2
    channel[occupied]=observed[occupied]/known[occupied]
    if np.min(abs(channel[occupied]))<1e-12:
        raise ValueError('L-SIG channel unobservable')
    symbol=np.fft.fft(corrected[start+16:start+80])/channel
    phase=np.angle(np.sum(symbol[pilots]*np.array([1,1,1,-1])))
    values=(symbol[data]*np.exp(-1j*phase)).real
    permutation=3*(np.arange(48)%16)+np.arange(48)//16
    # Legacy BPSK maps bit0 to -1 and bit1 to +1.
    soft=values[permutation]/max(float(np.mean(abs(values))),1e-12)
    bits=decode(soft)
    rate=int(bits[:4]@(1<<np.arange(4)))
    rates={11:6,15:9,10:12,14:18,9:24,13:36,8:48,12:54}
    if rate not in rates or bits[4] or np.sum(bits[:18])%2 or np.any(bits[18:]):
        raise ValueError('Invalid L-SIG rate/reserved/parity/tail')
    return dict(rate_mbps=rates[rate],length_octets=int(bits[5:17]@(1<<np.arange(12))))


def decode_legacy_data(corrected,start,header,*,frequency_measurement=None):
    """Legacy OFDM DATA recovery; received L-SIG supplies rate and length.

    Pilot phase is unwrapped modulo pi, assuming residual rotation between
    symbols stays below pi/2. This conditional receiver is not a full modem.
    """
    rates={6:(1,24,[1,1]),9:(1,36,[1,1,1,0,0,1]),
           12:(2,48,[1,1]),18:(2,72,[1,1,1,0,0,1]),
           24:(4,96,[1,1]),36:(4,144,[1,1,1,0,0,1]),
           48:(6,192,[1,1,1,0]),54:(6,216,[1,1,1,0,0,1])}
    n,dbps,mask=rates[header['rate_mbps']]
    labels=(np.arange(2**n)[:,None]>>np.arange(n))&1
    signed=2*labels-1
    def axis(bits):
        magnitude=np.ones(len(bits))
        for column in range(bits.shape[1]-1,0,-1):
            magnitude=2**(bits.shape[1]-column)-bits[:,column]*magnitude
        return bits[:,0]*magnitude
    if n==1:points=signed[:,0].astype(complex)
    else:points=(axis(signed[:,:n//2])+1j*axis(signed[:,n//2:]))/math.sqrt({2:2,4:10,6:42}[n])
    length=header['length_octets'];n_bits=16+8*length+6
    count=math.ceil(n_bits/dbps)
    if len(corrected)<start+80*(count+1):raise ValueError('Incomplete DATA')
    _,ltf=legacy_preamble();known=np.fft.fft(ltf)
    occupied=np.r_[np.arange(-26,0),np.arange(1,27)]%64
    pilots=np.array([-21,-7,7,21])%64
    data=np.array([k for k in range(-26,27) if k not in (0,-21,-7,7,21)])%64
    channel=np.ones(64,complex)
    training=(np.fft.fft(corrected[start-128:start-64])+np.fft.fft(corrected[start-64:start]))/2
    channel[occupied]=training[occupied]/known[occupied]
    if np.min(abs(channel[occupied]))<1e-12:raise ValueError('DATA channel unobservable')
    cbps=48*n;k=np.arange(cbps);first=(cbps//16)*(k%16)+k//16;s=max(n//2,1)
    permutation=s*(first//s)+(first+cbps-(16*first)//cbps)%s
    soft=[];previous=0.;phases=[]
    for index in range(count):
        begin=start+80*(index+1)+16
        spectrum=np.fft.fft(corrected[begin:begin+64])/channel
        raw=np.angle(np.sum(spectrum[pilots]*np.array([1,1,1,-1])))
        phase=previous+.5*np.angle(np.exp(2j*(raw-previous)));previous=phase
        phases.append(phase)
        values=spectrum[data]*np.exp(-1j*phase)
        # Pilot magnitude fixes the arbitrary L-LTF normalization without
        # learning constellation levels or gain from the expected payload.
        pilot_gain=float(np.mean(abs(spectrum[pilots])))
        if pilot_gain<1e-12:raise ValueError('DATA pilots unobservable')
        values/=pilot_gain
        distance=abs(values[:,None]-points[None,:])**2
        evidence=np.empty((48,n))
        for bit in range(n):
            evidence[:,bit]=np.min(distance[:,labels[:,bit]==0],axis=1)-np.min(distance[:,labels[:,bit]==1],axis=1)
        soft.extend(evidence.ravel()[permutation])
    # Depuncture before terminating at the six zero tail bits; padding follows.
    expanded=np.zeros(2*count*dbps)
    expanded[np.resize(np.asarray(mask,bool),len(expanded))]=soft
    scrambled=decode(expanded[:2*n_bits])
    candidates=[]
    for seed in range(1,128):
        state=seed;sequence=[]
        for _ in range(16+8*length):
            feedback=((state>>6)^(state>>3))&1
            sequence.append(feedback);state=((state<<1)|feedback)&127
        plain=scrambled[:len(sequence)]^np.asarray(sequence,dtype=np.uint8)
        if np.all(plain[:16]==0):candidates.append(plain[16:])
    if len(candidates)!=1:raise ValueError('SERVICE/scrambler recovery failed')
    payload=np.packbits(candidates[0],bitorder='little').tobytes()
    crc_ok=len(payload)>=4 and zlib.crc32(payload[:-4])==int.from_bytes(payload[-4:],'little')
    if frequency_measurement is not None:
        tail=min(count,8)
        frequency_measurement['tail_pilot_cfo_hz']=(float(np.polyfit(
            np.arange(tail)*4e-6,phases[-tail:],1)[0]/(2*np.pi)) if tail>=2 else None)
    return payload,crc_ok


def run(reference_tools,*,rx_cutoff_hz=9.53125e6,tx_candidate=False,tx_cutoff_scale=1.,track_pilots=None,resampler_span=None,resampler_fraction_bits=None,dac_enob=None,integrator_ratio=None,amplitude=.12,pa_input_p1db_envelope=None,tx_data_check=False,wanted_dbm=-50.,blocker_dbm=-50.,pga_db=27.,tx_rx_coupling=0.,clock_seed=None,converter_jitter_ps=0.,recovery_bounds=None,pa_input_loss_db=0.,pa_phase_deg_at_p1db=0.,design=None):
    from design_definition import load_design
    design=load_design() if design is None else design
    policy=design.architecture['rf_interoperability']['fpga_tx_preparation']
    track_pilots=policy['received_pilot_frequency_update'] if track_pilots is None else track_pilots
    resampler_span=policy['polyphase_resampler_span'] if resampler_span is None else resampler_span
    resampler_fraction_bits=policy['polyphase_resampler_fraction_bits'] if resampler_fraction_bits is None else resampler_fraction_bits
    dac_enob=design.architecture['model_assumptions']['paired_dac']['parameters']['enob'] if dac_enob is None else dac_enob
    if not np.isfinite(pa_phase_deg_at_p1db) or (pa_phase_deg_at_p1db and pa_input_p1db_envelope is None):
        raise ValueError('Finite PA phase hypothesis requires a PA threshold')
    if not np.isfinite(pa_input_loss_db) or pa_input_loss_db<0 or (pa_input_loss_db and pa_input_p1db_envelope is None):
        raise ValueError('External TX attenuation requires finite nonnegative loss and a PA threshold')
    if not np.isfinite(tx_rx_coupling) or tx_rx_coupling<0:
        raise ValueError('Finite nonnegative effective leakage required')
    if not all(np.isfinite(v) for v in (wanted_dbm,blocker_dbm,pga_db)):
        raise ValueError('Finite RX wanted/blocker/gain settings required')
    if not np.isfinite(rx_cutoff_hz) or rx_cutoff_hz<=0:
        raise ValueError('Positive finite RX cutoff required')
    if not np.isfinite(tx_cutoff_scale) or tx_cutoff_scale<=0:raise ValueError('TX cutoff scale')
    if not tx_candidate and tx_cutoff_scale!=1.:raise ValueError('TX cutoff scale requires candidate mode')
    if recovery_bounds is not None:
        required={'initial_residual_dbm','steady_residual_dbm','allowed_residual_dbm',
                  'recovery_tau_s','tx_tail_s','switch_s','receive_pipeline_s','reserve_s'}
        if not tx_data_check or not isinstance(recovery_bounds,dict) or set(recovery_bounds)!=required:
            raise ValueError('Return-DATA check and complete explicit recovery bounds required')
    if clock_seed is None and converter_jitter_ps!=0:
        raise ValueError('Converter jitter requires explicit clock-seed hypothesis')
    root=Path(reference_tools).resolve()
    revision=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()
    if revision!='dc93c8f30de46082690d5768d6ad03ea2c11e2cb':
        raise ValueError('Reference checkout does not match qualified revision')
    if subprocess.check_output(['git','-C',str(root),'status','--porcelain','--untracked-files=no'],text=True).strip():
        raise ValueError('Independent reference checkout has modified tracked files')
    sys.path.insert(0,str(root))
    import phy80211
    import phy80211header as h
    from he64_packet import parameters
    # VHT80 1SS has the same 234-tone/Ncol26 BCC geometry as HE RU242.
    for mcs in range(8):
        n,dbps,puncture,permutation,_,_=parameters(mcs)
        geometry=h.modulation(phyFormat=h.F.VHT,mcs=mcs,bw=h.BW.BW80,nSTS=1,shortGi=False)
        geometry.nSym=1
        if geometry.nDBPS!=dbps:raise ValueError('MCS geometry mismatch')
        labels=np.arange(234*n)
        expected=np.empty(234*n,int);expected[permutation]=labels
        independent=h.procInterleaveNonLegacy([labels.tolist()],geometry)[0]
        if not np.array_equal(expected,independent):raise ValueError('BCC interleaver reference mismatch')
    correction=None
    if tx_candidate:
        from rf_filter_tradeoff import tx_preemphasis_coefficients
        coefficients,delay,_=tx_preemphasis_coefficients(resampler_span=resampler_span,resampler_fraction_bits=resampler_fraction_bits,integrator_ratio=integrator_ratio)
        correction=(coefficients,delay)
    rows=[]
    header=bytes.fromhex('080200000200000000020200000000010200000000030000')
    cases=[(mcs,'data_MPDU',header+bytes(range(100))) for mcs in range(8)]
    # ACK: Frame Control, Duration, receiver address, then externally checked FCS.
    cases.append((0,'ACK',bytes.fromhex('d4000000020000000001')))
    for mcs,kind,body in cases:
        transmitter=phy80211.phy80211(ifDebug=False)
        psdu=body+zlib.crc32(body).to_bytes(4,'little')
        transmitter.genFromMpdu(psdu,h.modulation(
            phyFormat=h.F.L,mcs=mcs,bw=h.BW.BW20,nSTS=1,shortGi=False))
        wave=np.asarray(transmitter.genFinalSig(multiplier=1.,cfoHz=43000.,
            num=1,gap=False)[0])
        wave/=np.sqrt(np.mean(abs(wave)**2))
        drive=resample_poly(np.r_[np.zeros(73),wave,np.zeros(32)],4,1)
        bench=ClientBench(design=design);bench.track_rx_pilot_cfo=track_pilots;bench.tx_resampler_span=resampler_span;bench.rf.rx_cutoff_hz=rx_cutoff_hz
        bench.tx_resampler_fraction_bits=resampler_fraction_bits;bench.rf.dac_enob=dac_enob
        bench.rf.pa_input_p1db_envelope=pa_input_p1db_envelope
        bench.rf.pa_input_loss_db=pa_input_loss_db
        bench.rf.pa_phase_deg_at_p1db=pa_phase_deg_at_p1db
        bench.rf.tx_to_rx_filter_coupling=tx_rx_coupling
        clock_hypothesis=(bench.rf.configure_clock_noise(seed=clock_seed,converter_jitter_ps=converter_jitter_ps)
                          if clock_seed is not None else None)
        bench.rf.wanted_dbm=wanted_dbm;bench.rf.blocker_dbm=blocker_dbm;bench.rf.pga_db=pga_db
        bench.rf.tx_integrator_ratio=integrator_ratio
        if tx_candidate:
            bench.rf.tx_family='rx_all_pole_control'
            bench.rf.tx_cutoff_hz=12e6*tx_cutoff_scale
            bench.tx_preemphasis=correction
        capture=bench.receive_waveform(drive,tail_s=32/20e6)
        result,corrected=acquire(capture,valid=bench.last_rx_valid)
        if corrected is None:raise ValueError('Independent training not acquired')
        if not np.all(bench.last_rx_valid[result['data_start_sample']:]):
            raise ValueError('Gain discontinuity in independent legacy payload capture')
        header=decode_legacy_signal(corrected,result['data_start_sample'])
        if header!={'rate_mbps':(6,9,12,18,24,36,48,54)[mcs],'length_octets':len(psdu)}:
            raise ValueError('Independent L-SIG decode mismatch')
        frequency={}
        recovered,crc_ok=decode_legacy_data(corrected,result['data_start_sample'],header,frequency_measurement=frequency)
        if recovered!=psdu or not crc_ok:raise ValueError(f'Independent DATA decode mismatch at legacy MCS{mcs}')
        data_checked=True
        request_delivery=dict(bench.last_rx_delivery)
        return_ack=None
        reply=None
        if kind=='data_MPDU':
            ack_body=bytes.fromhex('d4000000020000000001')
            ack=ack_body+zlib.crc32(ack_body).to_bytes(4,'little')
            tx=phy80211.phy80211(ifDebug=False)
            transmit_psdu=psdu if tx_data_check else ack
            transmit_mcs=mcs if tx_data_check else 0
            tx.genFromMpdu(transmit_psdu,h.modulation(phyFormat=h.F.L,mcs=transmit_mcs,bw=h.BW.BW20,nSTS=1,shortGi=False))
            ack_wave=np.asarray(tx.genFinalSig(multiplier=1.,cfoHz=0.,num=1,gap=False)[0])
            ack_wave/=np.sqrt(np.mean(abs(ack_wave)**2))
            def peer_decode(samples):
                # Receiver-only capture padding; does not alter transmitted timing.
                acq,fixed=acquire(np.r_[np.zeros(73),samples,np.zeros(32)])
                if fixed is None:raise ValueError('Peer TX acquisition failed')
                signal=decode_legacy_signal(fixed,acq['data_start_sample'])
                if signal!={'rate_mbps':(6,9,12,18,24,36,48,54)[transmit_mcs],'length_octets':len(transmit_psdu)}:
                    raise ValueError('Peer TX L-SIG mismatch')
                measured={}
                recovered,crc=decode_legacy_data(fixed,acq['data_start_sample'],signal,frequency_measurement=measured)
                residual=measured['tail_pilot_cfo_hz']
                return dict(payload=recovered,crc_ok=crc,pilot_frequency_offset_hz=(
                    acq['estimated_cfo_hz']+residual if residual is not None else None))
            bench.measured_cfo_hz=result['estimated_cfo_hz']
            if track_pilots and crc_ok and frequency['tail_pilot_cfo_hz'] is not None:
                bench.measured_cfo_hz+=frequency['tail_pilot_cfo_hz']
            try:
                bench.transmit_intent('independent_DATA_PHY_check' if tx_data_check else 'independent_ACK',transmit_psdu,samples20=ack_wave,decode_samples=peer_decode,amplitude=amplitude)
                reply=bench.rows[-1]
                if tx_data_check:
                    peer=phy80211.phy80211(ifDebug=False)
                    peer.genFromMpdu(ack,h.modulation(phyFormat=h.F.L,mcs=0,bw=h.BW.BW20,nSTS=1,shortGi=False))
                    peer_wave=np.asarray(peer.genFinalSig(multiplier=1.,cfoHz=43000.,num=1,gap=False)[0])
                    peer_wave/=np.sqrt(np.mean(abs(peer_wave)**2))
                    # Start capture before the real ACK preamble. The timestamp
                    # is relative to the antenna packet marker plus its duration,
                    # not to the end of the queued DAC/FIR tail.
                    recovery_admission=None
                    if recovery_bounds is not None:
                        from rf_quality_budget import receiver_recovery_admission,frontend_recovery_budget
                        bounds=dict(recovery_bounds)
                        fixed=receiver_recovery_admission(peer_gap_s=10e-6,recovery_s=0.,
                            **{key:bounds.pop(key) for key in ('tx_tail_s','switch_s','receive_pipeline_s','reserve_s')})
                        if fixed['available_recovery_s']<0:
                            raise ValueError('RX recovery fixed timing exceeds peer gap')
                        recovery_admission=frontend_recovery_budget(**bounds,switch_settle_s=0.,
                            available_s=fixed['available_recovery_s'])
                        if not recovery_admission['admitted']:
                            raise ValueError('RX residual recovery exceeds peer-gap allocation')
                    ack_start=reply['antenna_packet_end_s']+10e-6
                    capture_start=ack_start-73/20e6
                    if bench.chip.time-bench.origin>capture_start:
                        raise ValueError('RX recovery missed ACK capture start')
                    bench.advance(capture_start)
                    capture=bench.receive_waveform(resample_poly(np.r_[np.zeros(73),peer_wave,np.zeros(32)],4,1),tail_s=32/20e6)
                    acq,fixed=acquire(capture,valid=bench.last_rx_valid)
                    if fixed is None:raise ValueError('Return ACK acquisition failed')
                    if not np.all(bench.last_rx_valid[acq['data_start_sample']:]):
                        raise ValueError('Gain discontinuity in return ACK capture')
                    signal=decode_legacy_signal(fixed,acq['data_start_sample'])
                    decoded,valid_crc=decode_legacy_data(fixed,acq['data_start_sample'],signal)
                    if signal!={'rate_mbps':6,'length_octets':len(ack)} or decoded!=ack or not valid_crc:
                        raise ValueError('Return ACK header/payload/CRC mismatch')
                    return_ack=dict(recovery_admission=recovery_admission,crc_ok=True,max_tx_leak_filter_input_v=bench.rf.max_tx_leak_filter_input_v,scheduled_antenna_gap_s=10e-6,
                        rx_delivery=dict(bench.last_rx_delivery),queue_high_bits=bench.chip.stream['high'])
            except ValueError as error:
                reply=dict(crc_ok=False,failure=str(error))
        rows.append(dict(maximum_clock_error_s=bench.rf.max_clock_error_s,return_ack=return_ack,rx_delivery=request_delivery,frequency_measurement=frequency,reply=reply,kind=kind,data_crc_checked=data_checked,legacy_mcs=mcs,waveform_samples=len(wave),
            acquisition=result,header=header,queue_high_bits=bench.chip.stream['high'],
            adc_clipped_pairs=bench.rf.clips))
    return dict(design_provenance=design.provenance(),reference_revision=revision,reference_tracked_files_clean=True,pa_phase_deg_at_p1db=pa_phase_deg_at_p1db,pa_input_loss_db=pa_input_loss_db,recovery_bounds=recovery_bounds,clock_hypothesis=clock_hypothesis,tx_rx_coupling=tx_rx_coupling,wanted_dbm=wanted_dbm,blocker_dbm=blocker_dbm,pga_db=pga_db,tx_data_check=tx_data_check,tx_sequence_scope=('Scheduled DATA PHY check followed by peer ACK on retained RF state; initial DATA-to-DATA stimulus is not a MAC exchange' if tx_data_check else 'DATA-to-ACK response'),pa_input_p1db_envelope=pa_input_p1db_envelope,dac_enob=dac_enob,integrator_ratio=integrator_ratio,amplitude=amplitude,resampler_fraction_bits=resampler_fraction_bits,completed=all(row['reply'] is None or row['reply']['crc_ok'] for row in rows),resampler_span=resampler_span,track_pilots=track_pilots,rx_cutoff_hz=rx_cutoff_hz,tx_candidate=tx_candidate,tx_cutoff_scale=tx_cutoff_scale,source='https://github.com/cloud9477/gr-ieee80211/tree/dc93c8f30de46082690d5768d6ad03ea2c11e2cb',
        scope='Independent complete legacy PHY waveforms through shared RF/converters/queues; '
              'training and L-SIG checked; valid-format data/ACK MPDUs, ideal MAC decisions. '
              'All legacy OFDM rates DATA CRC checked; DSSS/CCK and HE unqualified.',rows=rows)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-tools',required=True)
    parser.add_argument('--rx-cutoff-hz',type=float,default=9.53125e6,
        help='Actual analog cutoff for tolerance/candidate screening; does not select hardware')
    parser.add_argument('--tx-candidate',action='store_true',help='Five-pole12MHz plus FPGA49-tap assumed correction')
    parser.add_argument('--tx-cutoff-scale',type=float,default=1.)
    parser.add_argument('--track-pilots',action=argparse.BooleanOptionalAction,default=None)
    parser.add_argument('--resampler-span',type=int,help='Diagnostic interpolation span override; default uses selected FPGA policy')
    parser.add_argument('--resampler-fraction-bits',type=int)
    parser.add_argument('--dac-enob',type=float,help='Explicit diagnostic DAC noise override; default uses selected design')
    parser.add_argument('--integrator-ratio',type=float)
    parser.add_argument('--amplitude',type=float,default=.12)
    parser.add_argument('--pa-input-p1db-envelope',type=float)
    parser.add_argument('--pa-input-loss-db',type=float,default=0.)
    parser.add_argument('--pa-phase-deg-at-p1db',type=float,default=0.)
    parser.add_argument('--wanted-dbm',type=float,default=-50.)
    parser.add_argument('--blocker-dbm',type=float,default=-50.)
    parser.add_argument('--pga-db',type=float,default=27.)
    parser.add_argument('--clock-seed',type=int)
    parser.add_argument('--converter-jitter-ps',type=float,default=0.)
    parser.add_argument('--recovery-bounds',type=json.loads,help='Explicit JSON residual/timing bounds; admission screen, not nonlinear recovery simulation')
    parser.add_argument('--tx-rx-coupling',type=float,default=0.,help='Effective TX-envelope to RX-filter voltage ratio; no overload recovery implied')
    parser.add_argument('--tx-data-check',action='store_true',help='Exercise TX DATA at every legacy rate; scheduled PHY check, not MAC lifecycle')
    args=parser.parse_args()
    print(json.dumps(run(args.reference_tools,rx_cutoff_hz=args.rx_cutoff_hz,tx_candidate=args.tx_candidate,tx_cutoff_scale=args.tx_cutoff_scale,track_pilots=args.track_pilots,resampler_span=args.resampler_span,resampler_fraction_bits=args.resampler_fraction_bits,dac_enob=args.dac_enob,integrator_ratio=args.integrator_ratio,amplitude=args.amplitude,pa_input_p1db_envelope=args.pa_input_p1db_envelope,tx_data_check=args.tx_data_check,wanted_dbm=args.wanted_dbm,blocker_dbm=args.blocker_dbm,pga_db=args.pga_db,tx_rx_coupling=args.tx_rx_coupling,clock_seed=args.clock_seed,converter_jitter_ps=args.converter_jitter_ps,recovery_bounds=args.recovery_bounds,pa_input_loss_db=args.pa_input_loss_db,pa_phase_deg_at_p1db=args.pa_phase_deg_at_p1db),indent=2))
