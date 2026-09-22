"""Ideal signal paths through timed, payload-bearing bidirectional host transport.

First connected increment. RF is a complex envelope; wired sampling has ideal
clock alignment. This does not implement autonomous acquisition or mode changes.
"""
from collections import deque
from fractions import Fraction
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
from rf_blocks import tone_response, held_response, controls, cascade_held_response, cascade_controls, mixed_cascade, mixer_controls, iq_error, iq_controls
from wired_blocks import WiredChannel, controls as wired_controls
from recovered_clock import framed_words
from framing import controls as framing_controls
from pacing import RationalPacer, RATIOS, controls as pacing_controls

P = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(P/'verification'))
from stream_codec import encode, Receiver, slots
from loopback_return import return_samples
from pilot import estimate as estimate_pilot, controls as pilot_controls, modulation_controls
from session import Session, controls as session_controls

class Packer:
    """LSB-first continuous bit stream, with no per-sample padding."""
    def __init__(self):
        self.value = self.count = 0
    def push(self, value, width, output_width):
        assert 0 <= value < 1 << width
        self.value |= int(value) << self.count
        self.count += width
        words = []
        while self.count >= output_width:
            words.append(self.value & ((1 << output_width)-1))
            self.value >>= output_width
            self.count -= output_width
        return words


def encode_iq(z,bits):
    scale=1 << (bits-1);mask=(1 << bits)-1
    i=int(np.clip(np.rint(z.real*scale),-scale,scale-1))
    q=int(np.clip(np.rint(z.imag*scale),-scale,scale-1))
    return (i & mask) | ((q & mask) << bits)


def decode_iq(word,bits):
    scale=1 << (bits-1);mask=(1 << bits)-1
    def signed(value):return value-(1 << bits) if value & scale else value
    return complex(signed(word & mask)/scale,signed((word >> bits)&mask)/scale)


def waveform(index, fs, bits, direction, bandwidth_hz=10e6, modulated=False, symbol_samples=8):
    # External test partner tone. No RF carrier timesteps are required.
    phase = 2*np.pi*1e6*index/fs + (.37 if direction == 'h2d' else 0)
    z = (tone_response(index/fs,.6,1e6,bandwidth_hz) if direction=='d2h'
         else .6*np.exp(1j*phase))
    if modulated and direction=='h2d' and index>=512:
        symbol=(index-512)//symbol_samples
        label=((symbol*13)^(symbol>>2)^2)&3
        z=.6*np.exp(.37j)*complex(1-2*(label&1),1-2*((label>>1)&1))/np.sqrt(2)
    return encode_iq(z,bits), z


def paced_sink(values, arrivals, period, duration, start_delay, capacity_samples=None):
    """Merge actual arrivals and independently scheduled consumption deadlines.

    An arrival exactly at a deadline is available. Missing data records an
    underflow; no sample is synthesized and no consumption clock is stalled.
    """
    events=[(Fraction(t),0,value) for t,value in zip(arrivals,values)]
    index=0
    while index*period < duration:
        events.append((start_delay+index*period,1,index))
        index+=1
    assert capacity_samples is None or capacity_samples>0
    fifo=deque();peak=0;underflows=[];overflows=[];output=[]
    for when,kind,value in sorted(events):
        if kind==0:
            if capacity_samples is not None and len(fifo)>=capacity_samples:
                overflows.append((when,value))
            else:
                fifo.append(value);peak=max(peak,len(fifo))
        elif fifo:
            output.append((value,when,fifo.popleft()))
        else:
            underflows.append(value)
    assert len(values)==len(output)+len(fifo)+len(overflows)
    return dict(output=output,underflows=underflows,overflows=overflows,peak_samples=peak,
                remaining_samples=len(fifo))


def run(mode_index, contract, frames=625, phase_ui=.3, period_ppm=100, h2d_ppm=0, h2d_phase=Fraction(0), visibility_cycles=2, modulated=False, iq_error_sign=0, iq_phase_sign=None, symbol_samples=8):
    mode = contract['modes'][mode_index]
    profile = contract['transport']['profiles'][mode['profile']]
    word_rate = profile['clock_hz']*profile['edges']
    plan = slots(mode_index)
    source = {s['id']:s for s in mode['sources']}
    fs = source['iq']['rate_bps']//source['iq']['sample_bits']
    bits = source['iq']['sample_bits']//2
    assert fs*2*bits == source['iq']['rate_bps']
    stop=frames*64
    wire_count=int(np.ceil(stop*source['wire']['rate_bps']/(10*word_rate)))
    wire_truth=[((i*713)^(i>>3)^0x2aa)&1023 for i in range(wire_count)]
    wire_values,wire_times,wire_report=framed_words(wire_truth,source['wire']['rate_bps'],phase_ui,period_ppm)
    assert wire_values==wire_truth
    lifecycle=Session();lifecycle.configure(mode_index)
    # Host training and RF lock are explicit ideal readiness inputs at this stage.
    lifecycle.host_ready=True
    lifecycle.ready['rf']=True
    lifecycle.ready['wire']=wire_report['marker_acquired_relative_payload_s']<=0
    lifecycle.arm()
    wire_events=deque(zip(wire_times*word_rate,wire_values))
    ratios=RATIOS[mode['id']]
    for name,spec in source.items():
        assert Fraction(*ratios[name])*word_rate==Fraction(spec['rate_bps'],spec['sample_bits'])
    pacers={name:RationalPacer(*ratio) for name,ratio in ratios.items()}
    directions = {}
    for direction in ('d2h', 'h2d'):
        directions[direction] = dict(
            pending=deque(), receiver=Receiver(mode_index), packed={k:Packer() for k in source},
            unpacked={k:Packer() for k in source}, queues={k:deque() for k in source},
            last_reference_tick={k:-1 for k in source},next_time={k:Fraction(0) for k in source},
            generated={k:[] for k in source}, recovered={k:[] for k in source},
            recovered_ticks={k:[] for k in source},
            command_events=[],prepared_command=(0,0),peak={k:0 for k in source}, frame=None,prepared={'wire':[],'iq':[]})
    stop = frames*64
    # Drain after finite stimulus. This tests finite transfer, not infinite stability.
    assert isinstance(visibility_cycles,int) and visibility_cycles>=0
    h2d_period=Fraction(1000000,1000000+h2d_ppm)
    events=sorted([(Fraction(k),'d2h',k) for k in range(stop+8*64)]+
                  [(h2d_phase+k*h2d_period,'h2d',k) for k in range(stop+8*64)])
    for tick,direction,word_index in events:
        state=directions[direction]
        assert lifecycle.mode==mode_index and all(lifecycle.enabled(k) for k in ('rf','wire'))
        for name, spec in source.items():
            period = Fraction(spec['sample_bits']*word_rate, spec['rate_bps'])
            if direction=='d2h' and name=='wire':
                while wire_events and wire_events[0][0]<=tick:
                    _,value=wire_events.popleft()
                    state['generated'][name].append(value)
                    state['queues'][name].append(value)
                state['peak'][name]=max(state['peak'][name],len(state['queues'][name])*10)
                continue
            due=0
            if direction=='h2d':
                # Payload enable history becomes visible only after destination delay.
                last=max(-1,min((tick-visibility_cycles*h2d_period)//1,stop-1))
                for reference_tick in range(state['last_reference_tick'][name]+1,last+1):
                    due+=pacers[name].tick()
                state['last_reference_tick'][name]=last
            while (due>0 if direction=='h2d' else tick<stop and state['next_time'][name]<=tick):
                if direction=='h2d':due-=1
                index = len(state['generated'][name])
                if name == 'iq':
                    value, _ = waveform(index, fs, bits, direction,modulated=modulated,symbol_samples=symbol_samples)
                else:
                    # Deterministic external serial-bit test source, packed into ten bits.
                    value = ((index*713) ^ (index >> 3) ^ (0x155 if direction=='h2d' else 0x2aa)) & 1023
                received=value
                state['generated'][name].append(value)
                words=state['packed'][name].push(received,spec['sample_bits'],10)
                if name=='wire' and direction=='d2h':
                    # Expose deserialized data only after the entire word arrives.
                    state['pending'].append((state['next_time'][name]+period,name,words))
                else:
                    state['queues'][name].extend(words)
                state['next_time'][name] += period
            state['peak'][name] = max(state['peak'][name],len(state['queues'][name])*10+state['packed'][name].count)
        while state['pending'] and state['pending'][0][0]<=tick:
            _,name,words=state['pending'].popleft()
            state['queues'][name].extend(words)
            state['peak'][name]=max(state['peak'][name],len(state['queues'][name])*10)
        if word_index % 64 == 0:
            selected = {}
            for name in source:
                q = state['queues'][name]
                selected[name] = [q.popleft() for _ in range(min(len(q),plan.count(name)))]
            state['frame'] = encode(mode_index,state['prepared']['wire'],state['prepared']['iq'],(word_index//64)%64,*state['prepared_command'])
            frame_index=word_index//64
            state['prepared_command']=((2,1) if frame_index==100 else (2,0) if frame_index==200 else (0,0)) if direction=='h2d' else (0,0)
            state['prepared']=selected
        event = state['receiver'].feed(state['frame'][word_index%64])
        if event and event[0]=='command' and event[1][0]!=0:
            state['command_events'].append((tick,*event[1]))
        if event and event[0] in source:
            name, value = event
            recovered = state['unpacked'][name].push(value,10,source[name]['sample_bits'])
            state['recovered'][name].extend(recovered)
            state['recovered_ticks'][name].extend([tick]*len(recovered))
    results = []
    for direction,state in directions.items():
        metrics = {}
        for name,spec in source.items():
            got = state['recovered'][name]
            sent = state['generated'][name]
            assert got == sent[:len(got)] and got
            assert not state['queues'][name]
            # A final partial ten-bit word is deliberately retained, not fabricated.
            remaining_bits = state['packed'][name].count+state['unpacked'][name].count
            assert len(sent)*spec['sample_bits'] == len(got)*spec['sample_bits']+remaining_bits
            assert len(sent)-len(got) <= 1
            period = Fraction(spec['sample_bits']*word_rate,spec['rate_bps'])
            latency = [float((Fraction(t)-i*period)/word_rate) for i,t in enumerate(state['recovered_ticks'][name])]
            metrics[name] = dict(generated_samples=len(sent),received_samples=len(got),
                remaining_bits=remaining_bits,payload_errors=0,peak_ingress_bits=state['peak'][name],
                maximum_delivery_latency_s=max(latency))
            if direction=='h2d':
                capacity=2048//spec['sample_bits']
                sink=paced_sink(got,state['recovered_ticks'][name],period,stop,Fraction(192),capacity)
                assert not sink['underflows'] and not sink['overflows'] and sink['remaining_samples']==0
                assert [v for _,_,v in sink['output']]==sent
                assert all(index==i and when==192+i*period
                           for i,(index,when,_) in enumerate(sink['output']))
                metrics[name]['transmit_sink']=dict(
                    startup_delay_s=192/word_rate,underflows=0,overflows=0,
                    capacity_samples=capacity,capacity_bits=capacity*spec['sample_bits'],
                    consumed_samples=len(sink['output']),peak_fifo_samples=sink['peak_samples'],
                    peak_fifo_bits=sink['peak_samples']*spec['sample_bits'],
                    remaining_samples=sink['remaining_samples'])
                # Negative control: consuming immediately must expose transport latency.
                early=paced_sink(got,state['recovered_ticks'][name],period,stop,Fraction(0))
                assert early['underflows']
                metrics[name]['zero_prefill_control_underflows']=len(early['underflows'])
                former=paced_sink(got,state['recovered_ticks'][name],period,stop,Fraction(128))
                metrics[name]['two_frame_prefill_underflows']=len(former['underflows'])
                if name=='iq':assert former['underflows']
                if name=='wire':
                    wire_tx=WiredChannel(spec['rate_bps'])
                    received_wire=[wire_tx.word(value) for _,_,value in sink['output']]
                    assert received_wire==sent
                    metrics[name]['external_wired_receiver']=wire_tx.report()
        if direction=='d2h':
            assert not wire_events and state['generated']['wire']==wire_truth
            metrics['wire']['wired_receiver']=wire_report
        scale=1 << (bits-1)
        decoded=np.array([decode_iq(v,bits) for v in state['recovered']['iq']])
        expected=np.array([waveform(i,fs,bits,direction,modulated=modulated,symbol_samples=symbol_samples)[1] for i in range(len(decoded))])
        error=decoded-expected
        assert np.max(abs(error.real)) <= .5/scale+1e-12
        assert np.max(abs(error.imag)) <= .5/scale+1e-12
        reconstruction=None
        loopbacks=[]
        if direction=='h2d':
            # Feed delivered samples at the proven DAC deadlines, not host arrival times.
            times=192/word_rate+np.arange(len(decoded))/fs
            commands=state['command_events']
            assert commands==[(h2d_phase+(101*64+4)*h2d_period,2,1),(h2d_phase+(201*64+4)*h2d_period,2,0)]
            # Apply accepted mute at the first DAC deadline at/after observation.
            muted=np.zeros(len(times),dtype=bool)
            for tick,op,arg in commands:
                assert op==2
                muted[times>=tick/word_rate]=bool(arg)
            assert muted.any() and (~muted).any()
            dac_values=np.where(muted,0j,decoded)
            ideal_values=np.where(muted,0j,expected)
            assert np.all(dac_values[muted]==0)
            actual=held_response(dac_values,times,10e6)
            ideal=held_response(ideal_values,times,10e6)
            reconstruction=dict(bandwidth_hz=10e6,
                mute_command_observation_ticks=[float(c[0]) for c in commands],
                muted_samples=int(muted.sum()),
                first_muted_sample=int(np.flatnonzero(muted)[0]),
                first_unmuted_sample_after_mute=int(np.flatnonzero(muted)[-1]+1),
                mute_semantics='Zero DAC samples at next sample boundary; queues and clocks continue.',
                rms_quantization_effect=float(np.sqrt(np.mean(abs(actual-ideal)**2))),
                output_peak=float(np.max(abs(actual))),
                observation='End of each DAC hold; zero initial filter state.')
            assert np.max(abs(actual-ideal))<=np.sqrt(2)*.5/scale+1e-12
            for attenuation in (.25,1):
                tuned_reference=cascade_held_response(ideal_values,times,10e6,attenuation)
                for offset in (-100e3,0,100e3):
                    rx=mixed_cascade(dac_values,times,10e6,attenuation,offset)
                    reference=mixed_cascade(ideal_values,times,10e6,attenuation,offset)
                    rx,iq_norm=iq_error(rx,.1*iq_error_sign,5*(iq_error_sign if iq_phase_sign is None else iq_phase_sign))
                    reference,_=iq_error(reference,.1*iq_error_sign,5*(iq_error_sign if iq_phase_sign is None else iq_phase_sign))
                    adc_words=[encode_iq(z,bits) for z in rx]
                    adc=np.array([decode_iq(v,bits) for v in adc_words])
                    assert np.max(abs(rx.real))<1 and np.max(abs(rx.imag))<1
                    bound=(1+iq_norm*attenuation)*np.sqrt(2)*.5/scale
                    assert np.max(abs(adc-reference))<=bound+1e-12
                    host_samples=[]
                    returned=return_samples(mode_index,adc_words,(times+1/fs)*word_rate,
                        2*bits,wire_values,wire_times*word_rate,capture=host_samples)
                    loopbacks.append(dict(external_amplitude_transmission=attenuation,
                        host_return=returned,lo_offset_hz=offset,
                        external_host_pilot=estimate_pilot([decode_iq(v,bits) for v in host_samples],fs,modulated=modulated,symbol_samples=symbol_samples),
                        rms_error_vs_zero_offset=float(np.sqrt(np.mean(abs(adc-tuned_reference)**2))),
                        adc_samples=len(adc_words),peak_analog_component=float(max(np.max(abs(rx.real)),np.max(abs(rx.imag)))),
                        rms_error_vs_filtered_ideal=float(np.sqrt(np.mean(abs(adc-reference)**2))),
                        maximum_error=float(np.max(abs(adc-reference))),quantization_bound=bound,
                        observation='ADC at end of each DAC hold; staged D2H return alongside wired RX.'))
        results.append(dict(direction=direction,streams=metrics,
            rf_reconstruction=reconstruction,rf_external_loopbacks=loopbacks,rx_bandwidth_hz=10e6 if direction=='d2h' else None,
            rf_quantization_rms_error=float(np.sqrt(np.mean(abs(error)**2))),
            rf_sample_rate_hz=fs,rf_bits_per_component=bits))
    return dict(mode=mode['id'],symbol_samples=symbol_samples,iq_gain_error=.1*iq_error_sign,iq_phase_error_deg=5*(iq_error_sign if iq_phase_sign is None else iq_phase_sign),rf_test_waveform='pilot_then_qpsk' if modulated else 'tone',lifecycle=dict(armed=lifecycle.armed,host_readiness='ideal external input',rf_readiness='ideal external input',wire_readiness='completed marker acquisition; no independent lock detector'),h2d_visibility_cycles=visibility_cycles,h2d_frequency_error_ppm=h2d_ppm,h2d_phase_ticks=float(h2d_phase),initial_wired_phase_ui=phase_ui,initial_wired_period_ppm=period_ppm,duration_s=stop/word_rate,host_payload_pacing_ratios=ratios,directions=results)


def main():
    ap=argparse.ArgumentParser()
    group=ap.add_mutually_exclusive_group()
    group.add_argument('--clock-sweep',action='store_true')
    group.add_argument('--host-clock-sweep',action='store_true')
    ap.add_argument('--iq-error-sign',type=int,choices=(-1,0,1),default=0)
    ap.add_argument('--iq-phase-sign',type=int,choices=(-1,0,1),default=None,
                    help='Independent phase mismatch sign; defaults to gain mismatch sign.')
    ap.add_argument('--modulated',action='store_true')
    ap.add_argument('--symbol-samples',type=int,choices=(2,4,8),default=8)
    ap.add_argument('--visibility-cycles',type=int,default=2)
    args=ap.parse_args()
    controls()
    cascade_controls()
    mixer_controls()
    iq_controls()
    pilot_controls()
    modulation_controls()
    session_controls()
    wired_controls()
    framing_controls()
    pacing_controls()
    # Explicit contract vectors avoid two matching-but-wrong codec conventions.
    assert encode_iq(complex(-1,.5),8)==0x4080
    assert decode_iq(0xff80,8)==complex(-1,-1/128)
    assert encode_iq(complex(-.5,-.25),12)==0xe00c00
    assert decode_iq(0xe00c00,12)==complex(-.5,-.25)
    assert encode_iq(0j,8)==0
    assert encode_iq(complex(2,-2),8)==0x807f
    # A corrupt command header must not reach the mute control.
    invalid=encode(0,[],[],0,2,1);invalid[0]^=1
    rx=Receiver(0);events=[]
    try:
        for word in invalid:events.append(rx.feed(word))
    except ValueError:
        assert rx.fault and not any(e is not None for e in events)
    else:
        raise AssertionError('Corrupt mute command was accepted')
    contract_path=P/'spec/contract.json'
    contract=json.loads(contract_path.read_text())
    # Hand-check packing across a word boundary, independently of round-trip code.
    pack=Packer()
    assert pack.push(0xabc,12,10)==[0x2bc]
    assert pack.push(0x123,12,10)==[0x08e]
    assert pack.value==1 and pack.count==4
    # Deadline ordering controls: a late arrival cannot satisfy an earlier sample.
    assert paced_sink([7],[1],Fraction(1),1,Fraction(0))['underflows']==[0]
    assert paced_sink([7],[1],Fraction(1),1,Fraction(1))['underflows']==[]
    settings=[(phase,ppm,0,Fraction(0)) for phase in (-.3,.3) for ppm in (-100,100)] if args.clock_sweep else [( .3,100,ppm,phase) for ppm in (-100,100) for phase in (Fraction(0),Fraction(1,3))] if args.host_clock_sweep else [(.3,100,0,Fraction(0))]
    drift_controls=[]
    for ppm in (-1000,0,1000):
        period=Fraction(1000000,1000000+ppm)
        test=paced_sink(list(range(10000)),range(10000),period,10000,Fraction(4),8)
        early_underflows=sum(4+i*period<9999 for i in test['underflows'])
        if ppm<0:assert test['overflows']
        elif ppm>0:assert early_underflows>0
        else:assert not test['overflows'] and not test['underflows']
        drift_controls.append(dict(consumer_frequency_error_ppm=ppm,
            pre_end_underflows=early_underflows,overflows=len(test['overflows']),
            peak_samples=test['peak_samples']))
    results=[]
    for i in range(len(contract['modes'])):
        for phase,ppm,hppm,hphase in settings:
            results.append(run(i,contract,phase_ui=phase,period_ppm=ppm,h2d_ppm=hppm,h2d_phase=hphase,visibility_cycles=args.visibility_cycles,modulated=args.modulated,iq_error_sign=args.iq_error_sign,iq_phase_sign=args.iq_phase_sign,symbol_samples=args.symbol_samples))
            print(contract['modes'][i]['id'],phase,ppm,hppm,str(hphase),'connected checks passed',flush=True)
    if args.modulated and args.symbol_samples==8 and args.iq_error_sign==0 and args.iq_phase_sign in (None,0):
        assert all(c['external_host_pilot']['symbol_errors']==0 for r in results for d in r['directions'] for c in d['rf_external_loopbacks'])
    report=dict(status='ideal_connected_payload_transport_increment',complete_architecture=False,
        source_hashes={str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
            [Path(__file__),Path(__file__).with_name('rf_blocks.py'),Path(__file__).with_name('wired_blocks.py'),Path(__file__).with_name('recovered_clock.py'),Path(__file__).with_name('framing.py'),Path(__file__).with_name('pacing.py'),Path(__file__).with_name('loopback_return.py'),Path(__file__).with_name('pilot.py'),Path(__file__).with_name('session.py'),P/'system_model/clock_tracking_screen.py',P/'system_model/wired_screen.py',contract_path,P/'verification/stream_codec.py',P/'verification/transport_model.py']},
        results=results,finite_fifo_drift_controls=drift_controls,limitations=[
            'RF RX and TX filters are hypothetical 10MHz one-pole envelopes; mixers and wired sampling remain ideal.',
            'RX wired clock tracks observed transitions; H2D phase/frequency differ from D2H. Reference-to-H2D visibility has a fixed configurable delay, not a metastability model.',
            'TX consumes exact-rate sample/word events after a chosen three-frame prefill; DAC holds drive an exact one-pole response; wired bits traverse a hypothetical one-pole channel with prescribed sampling phase.',
            'RF mute/unmute crosses validated host commands with ideal next-sample application; shared reset/mode changes, calibration, CDC latency, noise and supply coupling remain absent.',
            'Finite queue test includes one frame of snapshot staging; remaining RTL packer/CDC/pipeline delays are not qualified.',
            'TX payload pacing assumes exact chip TX/reference ratios. H2D service offsets are exercised; return-path CDC, variable synchronization delays, stalls and clock-ratio errors remain open.',
            'Contract converter widths are targets, not achieved transistor resolution.'])
    (P/(f'evidence/connected-platform-symbols-{args.symbol_samples}-gain-{args.iq_error_sign}-phase-{args.iq_phase_sign}.json' if args.symbol_samples!=8 else f'evidence/connected-platform-iq-gain-{args.iq_error_sign}-phase-{args.iq_phase_sign}.json' if args.iq_phase_sign is not None else f'evidence/connected-platform-iq-error-{args.iq_error_sign}.json' if args.iq_error_sign else 'evidence/connected-platform-modulated.json' if args.modulated else 'evidence/connected-platform-host-clock-sweep.json' if args.host_clock_sweep else 'evidence/connected-platform-clock-sweep.json' if args.clock_sweep else 'evidence/connected-platform.json')).write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':
    main()
