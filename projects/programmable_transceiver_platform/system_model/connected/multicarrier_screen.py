"""Bandwidth-defined RF supporting screen; not a Wi-Fi modem or transport test."""
from fractions import Fraction
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from rf_blocks import cascade_held_response
from chip_model import encode_iq, decode_iq, paced_sink
from loopback_return import return_samples
from recovered_clock import framed_words
from reference_memory import apply as reference_memory, controls as reference_controls


def run(noise_rms=0.0,noise_density=None,drive_rms=.18,adc_bits=None,reference_strength=0.0):
    reference_controls()
    assert np.isfinite(drive_rms) and drive_rms>0
    assert noise_density is None or (np.isfinite(noise_density) and noise_density>=0 and noise_rms==0)
    assert noise_rms>=0 and np.isfinite(noise_rms)
    rng=np.random.default_rng(680)
    bins=np.r_[np.arange(-26,0),np.arange(1,27)]
    labels=rng.integers(0,4,(40,len(bins)))
    symbols=((1-2*(labels&1))+1j*(1-2*((labels>>1)&1)))/np.sqrt(2)
    cases=[]
    root=Path(__file__).resolve().parents[2]
    contract=json.loads((root/'spec/contract.json').read_text())
    for fs,bits in ((20e6,8),(40e6,12)):
        conversion_bits=bits if adc_bits is None else adc_bits
        assert 2<=conversion_bits<=bits
        sample_noise_rms=noise_rms if noise_density is None else noise_density*np.sqrt(fs)
        n=int(fs/312500);cp=n//4
        spectrum=np.zeros((40,n),complex);spectrum[:,bins%n]=symbols
        base=np.fft.ifft(spectrum,axis=1)
        # Fixed RMS normalization; no data-dependent peak normalization.
        amplitude=drive_rms*n/np.sqrt(len(bins))
        base*=amplitude
        waveform=np.concatenate((base[:,-cp:],base),axis=1).ravel()
        scale=2**(bits-1)
        def clipping_count(z,precision=bits):
            scale=2**(precision-1)
            i=np.rint(z.real*scale);q=np.rint(z.imag*scale)
            return int(np.sum((i < -scale)|(i > scale-1)|(q < -scale)|(q > scale-1)))
        dac_clipped=clipping_count(waveform)
        def demod(z):
            return np.fft.fft(z.reshape(40,n+cp)[:,cp:],axis=1)[:,bins%n]/amplitude
        assert np.max(abs(demod(waveform)-symbols))<1e-14
        dac=np.array([decode_iq(encode_iq(z,bits),bits) for z in waveform])
        mode_index=0 if fs==40e6 else 1
        mode=contract['modes'][mode_index]
        sources={x['id']:x for x in mode['sources']}
        profile=contract['transport']['profiles'][mode['profile']]
        word_rate=profile['clock_hz']*profile['edges']
        assert sources['iq']['rate_bps']==fs*2*bits
        wire_rate=sources['wire']['rate_bps']
        wire_count=(len(waveform)*wire_rate+int(fs)*10-1)//(int(fs)*10)
        wire_truth=[((i*713)^(i>>3)^0x2aa)&1023 for i in range(wire_count)]
        wire_values,wire_times,wire_report=framed_words(wire_truth,wire_rate,.3,100)
        assert wire_values==wire_truth
        tx_words=[encode_iq(z,bits) for z in waveform]
        delivered=[];delivery_ticks=[]
        # Same framing engine in the opposite direction, with host producers
        # paced from the shared reference. No independent-clock CDC claim.
        tx_transport=return_samples(mode_index,tx_words,np.arange(len(tx_words))*word_rate/fs,
            2*bits,wire_truth,np.arange(wire_count)*10*word_rate/wire_rate,
            capture=delivered,capture_ticks=delivery_ticks)
        period=Fraction(word_rate,int(fs));duration=len(tx_words)*period
        sink=paced_sink(delivered,delivery_ticks,period,duration,Fraction(192),2048//(2*bits))
        assert not sink['underflows'] and not sink['overflows'] and not sink['remaining_samples']
        assert [x[2] for x in sink['output']]==tx_words
        negative=paced_sink(delivered,delivery_ticks,period,duration,Fraction(0),2048//(2*bits))
        assert negative['underflows']
        dac=np.array([decode_iq(x[2],bits) for x in sink['output']])
        dac_times=np.array([float(x[1])/word_rate for x in sink['output']])
        tx_report=dict(transport=tx_transport,prefill_ticks=192,
            peak_dac_fifo_samples=sink['peak_samples'],underflows=0,overflows=0,
            zero_prefill_underflows=len(negative['underflows']),
            scope='Shared-clock host framing and DAC pacing; wired TX words decoded but serializer not exercised here.')
        noise_rng=np.random.default_rng(683+int(fs))
        unit_noise=(noise_rng.normal(size=len(dac))+1j*noise_rng.normal(size=len(dac)))/np.sqrt(2)
        assert .95<float(np.mean(abs(unit_noise)**2))<1.05
        for attenuation in (.25,1):
            rx=cascade_held_response(dac,dac_times,10e6,attenuation)
            assert max(abs(rx.real).max(),abs(rx.imag).max())<1
            noise=sample_noise_rms*unit_noise
            adc_input=rx+noise
            adc_input,reference_spans=reference_memory(adc_input,fs,reference_strength)
            clipped=clipping_count(adc_input,conversion_bits)
            converted=[decode_iq(encode_iq(z,conversion_bits),conversion_bits) for z in adc_input]
            adc_words=[encode_iq(z,bits) for z in converted]
            assert all(decode_iq(w,bits)==z for w,z in zip(adc_words,converted))
            host_words=[]
            transport=return_samples(mode_index,adc_words,(dac_times+1/fs)*word_rate,
                2*bits,wire_values,wire_times*word_rate,capture=host_words)
            adc=np.array([decode_iq(z,bits) for z in host_words])
            received=demod(adc)
            # First two blocks are startup guard; eight training blocks.
            train=slice(2,10);test=slice(10,None)
            response=np.mean(received[train]*symbols[train].conj(),axis=0)
            assert np.min(abs(response))>1e-3
            corrected=received[test]/response
            rms=float(np.sqrt(np.mean(abs(corrected-symbols[test])**2)))
            decisions=(corrected.real<0).astype(int)+2*(corrected.imag<0).astype(int)
            # Tail perturbation cannot affect the frozen training coefficients.
            changed=received.copy();changed[10:]*=-1
            assert np.array_equal(response,np.mean(changed[train]*symbols[train].conj(),axis=0))
            assert np.sqrt(np.mean(abs(changed[test]/response-symbols[test])**2))>1
            cases.append(dict(reference_memory_strength=reference_strength,reference_memory_tau_s=50e-9,minimum_reference_span=float(min(reference_spans)),maximum_reference_span=float(max(reference_spans)),adc_quantizer_bits=conversion_bits,transport_component_bits=bits,drive_complex_rms_target=drive_rms,dac_clipped_pairs=dac_clipped,noise_complex_rms_target=sample_noise_rms,noise_complex_two_sided_density=sample_noise_rms/np.sqrt(fs),noise_bin_rms_before_equalizer=sample_noise_rms*np.sqrt(n)/amplitude,noise_complex_rms_measured=float(np.sqrt(np.mean(abs(noise)**2))),adc_clipped_pairs=clipped,mode=mode['id'],host_transmit=tx_report,host_return=transport,wire_recovery=wire_report,sample_rate_hz=fs,bits=bits,attenuation=attenuation,
                active_subcarrier_edge_hz=8125000,subcarrier_spacing_hz=312500,
                training_blocks=8,held_out_blocks=30,held_out_symbols=1560,
                dac_peak_component=float(max(abs(waveform.real).max(),abs(waveform.imag).max())),
                minimum_normalized_response=float(np.min(abs(response))/attenuation),
                maximum_normalized_response=float(np.max(abs(response))/attenuation),
                calibrated_rms_error=rms,symbol_errors=int(np.sum(decisions!=labels[test]))))
    p=Path(__file__).resolve().parents[2]
    report=dict(cases=cases,status='supporting_rf_bandwidth_screen',complete_architecture=False,
        limitations=['Both RF host directions framed; shared clocks only, no wired TX serializer or reset/mute in this screen.',
            'Ideal timing and LO; no I/Q mismatch, blockers or nonlinear compression. Injected IID complex noise is a sensitivity assumption, not a physical noise prediction.',
            'Active carriers span -8.125 to +8.125MHz; finite rectangular blocks have out-of-band sidelobes.',
            'No spectral mask, Wi-Fi packet format, coding, acquisition or compliance claim.',
            'Per-bin equalizer is external-host functionality; poles and converter widths remain hypothetical.'],
        source_hashes={str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in
            (Path(__file__).resolve(),Path(__file__).with_name('rf_blocks.py').resolve(),Path(__file__).with_name('reference_memory.py').resolve(),Path(__file__).with_name('chip_model.py').resolve(),Path(__file__).with_name('loopback_return.py').resolve(),Path(__file__).with_name('recovered_clock.py').resolve(),p/'verification/stream_codec.py',p/'system_model/clock_tracking_screen.py',p/'system_model/wired_screen.py',Path(__file__).with_name('framing.py').resolve(),p/'spec/contract.json')})
    (p/(f'evidence/connected-multicarrier-reference-{reference_strength:g}-adc-{adc_bits}-drive-{drive_rms:g}-noise-{noise_rms:g}-density-{noise_density}.json' if reference_strength else f'evidence/connected-multicarrier-adc-{adc_bits}-drive-{drive_rms:g}-noise-{noise_rms:g}-density-{noise_density}.json' if adc_bits is not None else f'evidence/connected-multicarrier-drive-{drive_rms:g}-noise-{noise_rms:g}-density-{noise_density}.json' if drive_rms!=.18 else f'evidence/connected-multicarrier-density-{noise_density:g}.json' if noise_density is not None else 'evidence/connected-multicarrier-screen.json' if noise_rms==0 else f'evidence/connected-multicarrier-noise-{noise_rms:g}.json')).write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(cases,indent=2))

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    group=ap.add_mutually_exclusive_group()
    group.add_argument('--noise-rms',type=float,default=0.0,help='ADC-input complex RMS in normalized full-scale component units.')
    group.add_argument('--noise-density',type=float,help='Square root of complex two-sided PSD in normalized units/sqrt(Hz). Flat over the sample Nyquist interval.')
    ap.add_argument('--drive-rms',type=float,default=.18,help='Fixed desired complex waveform RMS before DAC clipping.')
    ap.add_argument('--adc-bits',type=int,choices=(4,6,8),help='Ideal ADC quantizer precision; transport widths and sample rates stay fixed.')
    ap.add_argument('--reference-strength',type=float,default=0.0,help='Signed hypothetical reference-memory span coupling, magnitude below one.')
    args=ap.parse_args()
    run(args.noise_rms,args.noise_density,args.drive_rms,args.adc_bits,args.reference_strength)
