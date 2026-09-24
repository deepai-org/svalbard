"""External FPGA coordination of generic opaque-word PHY instances.

No video encoder or protocol selector is added to silicon. Prescribed forwarded
clock and skew are architecture hypotheses, not a PLL or package qualification.
"""
import math
import numpy as np


def current_sink_levels(current_a=.008, termination_ohm=50., termination_v=3.3):
    if not all(math.isfinite(v) and v>0 for v in (current_a,termination_ohm,termination_v)):
        raise ValueError('Positive finite electrical parameters required')
    low=termination_v-current_a*termination_ohm
    if low<0:raise ValueError('Sink lacks voltage compliance')
    return dict(high_v=termination_v,low_v=low,common_mode_v=(termination_v+low)/2,
        differential_magnitude_v=termination_v-low,sink_power_w=current_a*low,
        termination_power_w=current_a**2*termination_ohm,source_power_w=current_a*termination_v)


class ForwardedLaneGroup:
    """Board/FPGA supervisor for multiple single-lane chips, not on-chip logic."""
    def __init__(self,word_hz,lanes=3,width=10,*,chips=None):
        if not math.isfinite(word_hz) or word_hz<=0 or type(lanes) is not int or lanes<1 or width!=10:
            raise ValueError('Positive word clock and opaque ten-bit lanes required')
        self.word_hz=word_hz;self.lanes=lanes;self.width=width
        self.ui=1/(word_hz*width);self.armed=False;self.epoch=0
        self.chips=tuple(chips) if chips is not None else None
        if self.chips is not None and (len(self.chips)!=lanes or len({id(c) for c in self.chips})!=lanes):
            raise ValueError('One distinct chip per lane required')
        self.configuration_snapshot=None
    def configuration(self):
        if self.chips is None:return None
        result=[];directions=set()
        for chip in self.chips:
            interface=getattr(chip,'wire_interface',{})
            direction=(chip.wired_tx_enabled,chip.wired_rx_enabled)
            if (chip.active_engine!='wire' or chip.wire_rate_override!=self.word_hz*10 or
                chip.wired_pad_path!='serial' or chip.host_frame_words!=64 or
                interface.get('electrical')!='dc_current_sink' or
                interface.get('clock_source')!='forwarded_word' or
                interface.get('word_reference_hz')!=self.word_hz or
                direction not in ((True,False),(False,True))):
                raise ValueError('Incompatible lane resources')
            directions.add(direction)
            result.append((chip.resource_generation,getattr(chip,'wire_interface_generation',0),
                chip.epoch,direction))
        if len(directions)!=1:raise ValueError('Mixed source/sink lane directions')
        return tuple(result)
    def arm(self,ready):
        if self.armed or len(ready)!=self.lanes or not all(x is True for x in ready):
            raise ValueError('Every lane must qualify before group launch')
        self.configuration_snapshot=self.configuration()
        self.armed=True
    def stop(self):self.armed=False;self.epoch+=1
    def lose_reference(self,lane):
        if type(lane) is not int or not 0<=lane<self.lanes:raise ValueError('Invalid lane')
        self.stop()
    def align_captures(self,captures,*,epoch,depth=4):
        """Causal external FPGA deskew after a known common first-word epoch.

        Each lane supplies (arrival time, opaque word) pairs. No payload values
        are used to discover alignment. Finite queues wait for the slowest lane;
        this models an external sink able to accept every completed row.
        """
        from collections import deque
        if not self.armed or epoch!=self.epoch:raise ValueError('Inactive or stale capture epoch')
        try:
            if self.configuration()!=self.configuration_snapshot:
                raise ValueError('Lane configuration changed after launch')
        except ValueError:
            self.stop();raise
        if type(depth) is not int or depth<1 or len(captures)!=self.lanes:
            raise ValueError('Positive deskew depth and one stream per lane required')
        events=[]
        for lane,capture in enumerate(captures):
            previous=-math.inf
            for time,word in capture:
                if not math.isfinite(time) or time<=previous or not isinstance(word,(int,np.integer)) or not 0<=word<1024:
                    raise ValueError('Strictly increasing finite captures of ten-bit words required')
                events.append((time,lane,int(word)));previous=time
        queues=[deque() for _ in captures];high=[0]*self.lanes;rows=[];times=[]
        fault=None
        for time,lane,word in sorted(events):
            if len(queues[lane])==depth:
                fault='overflow';break
            queues[lane].append(word);high[lane]=max(high[lane],len(queues[lane]))
            if all(queues):
                rows.append([q.popleft() for q in queues]);times.append(time)
        pending=[len(q) for q in queues]
        if fault is None and any(pending):fault='incomplete'
        if fault is not None:self.stop()
        return dict(words=np.asarray(rows,dtype=int).reshape(-1,self.lanes),
            times_s=times,fault=fault,maximum_occupancy=high,pending_words=pending,
            depth=depth,epoch=epoch)

    def transfer(self,words,*,lane_skew_s,word_delays,deskew_capacity=4,clock_jitter_s=0.):
        if not self.armed:raise ValueError('Group not armed')
        try:
            if self.configuration()!=self.configuration_snapshot:
                raise ValueError('Lane configuration changed after launch')
        except ValueError:
            self.stop()
            raise
        data=np.asarray(words)
        if data.ndim!=2 or len(data)==0 or data.shape[1]!=self.lanes or data.dtype.kind not in 'iu' or np.any(data<0) or np.any(data>=1024):
            raise ValueError('One row of opaque ten-bit words per word clock required')
        if len(lane_skew_s)!=self.lanes or len(word_delays)!=self.lanes or not all(math.isfinite(x) for x in lane_skew_s):
            raise ValueError('One finite skew and integer delay per lane required')
        if type(deskew_capacity) is not int or deskew_capacity<0:
            raise ValueError("Nonnegative integer deskew capacity required")
        if any(type(d) is not int or not 0<=d<=deskew_capacity for d in word_delays):
            raise ValueError('Lane delay exceeds external deskew capacity')
        if not math.isfinite(clock_jitter_s) or abs(clock_jitter_s)>=self.ui/4:
            raise ValueError('Common-clock jitter outside timing envelope')
        recovered=[];n=len(data)*10
        # Each word has one common reference disturbance; keep all bit edges
        # monotonic. Relative lane skew remains visible to the receiver.
        jitter=clock_jitter_s*np.sin(np.arange(n)//10*math.pi/4)
        times=np.arange(n)*self.ui+jitter
        samples=times+self.ui/2
        for lane,skew in enumerate(lane_skew_s):
            bits=((data[:,lane,None]>>np.arange(10))&1).reshape(-1)
            delayed=np.r_[np.zeros(word_delays[lane]*10,dtype=int),bits]
            # External FPGA removes known whole-word delay; fractional skew
            # must still fit the eye and cannot be repaired by FIFO deskew.
            positions=np.searchsorted(times+skew,samples,side='right')-1
            observed=delayed[np.clip(positions+word_delays[lane]*10,0,len(delayed)-1)]
            recovered.append(observed.reshape(-1,10)@(1<<np.arange(10)))
        result=np.column_stack(recovered)
        return dict(words=result,word_errors=int(np.count_nonzero(result!=data)),
            serial_rate_bps=1/self.ui,aggregate_bps=self.lanes/self.ui,
            external_deskew_words=max(word_delays),epoch=self.epoch)


def pad_eye(bits, *, bit_rate, capacitance_f, resistance_ohm=50., current_a=.008,
            termination_v=3.3, sample_offset_ui=.5, minimum_differential_v=.1,switch_tau_s=0.):
    """Two terminated RC legs driven by an ideal complementary current sink.

    Exact piecewise exponential solution; capacitance includes pad/package/load.
    Optional first-order current switching; no transistor calibration, ESD,
    transmission-line or supply-noise model.
    """
    levels=current_sink_levels(current_a,resistance_ohm,termination_v)
    if not all(math.isfinite(x) and x>0 for x in (bit_rate,capacitance_f)):
        raise ValueError('Positive rate and capacitance required')
    if not 0<sample_offset_ui<1:raise ValueError('Sample must lie inside bit')
    if not math.isfinite(switch_tau_s) or switch_tau_s<0:
        raise ValueError('Nonnegative finite current-switch time constant required')
    state=np.full(2,termination_v);currents=np.zeros(2);samples=[]
    tau=resistance_ohm*capacitance_f;period=1/bit_rate
    for bit in bits:
        if bit not in (0,1):raise ValueError('Binary pad stimulus required')
        target=np.array([levels['high_v'],levels['low_v']])
        if not bit:target=target[::-1]
        commanded=(termination_v-target)/resistance_ohm
        def voltage(dt):
            decay=math.exp(-dt/tau)
            if switch_tau_s==0:extra=0.
            elif abs(switch_tau_s-tau)<1e-8*tau:
                extra=-resistance_ohm*(currents-commanded)*(dt/tau)*decay
            else:
                extra=-resistance_ohm*(currents-commanded)*switch_tau_s/(switch_tau_s-tau)*(math.exp(-dt/switch_tau_s)-decay)
            return target+(state-target)*decay+extra
        sample=voltage(sample_offset_ui*period)
        samples.append((sample[0]-sample[1])*(1 if bit else -1))
        state=voltage(period)
        currents=commanded if switch_tau_s==0 else commanded+(currents-commanded)*math.exp(-period/switch_tau_s)
    if not samples:raise ValueError('Nonempty stimulus required')
    return dict(minimum_signed_eye_v=float(min(samples)),
        passes=bool(min(samples)>=minimum_differential_v),rc_tau_s=tau,switch_tau_s=switch_tau_s)


def forwarded_clock_budget(word_hz, *, reference_error_s, pll_error_s,
                           distribution_skew_s, word_phase_error=0):
    """Worst-case error sum relative to connector forwarded clock, not RSS.

    PLL error is a prescribed residual envelope, not simulated acquisition.
    An integer-word phase error must be removed before launch by FPGA alignment.
    """
    terms=(reference_error_s,pll_error_s,distribution_skew_s)
    if not math.isfinite(word_hz) or word_hz<=0 or any(not math.isfinite(x) or x<0 for x in terms):
        raise ValueError('Finite nonnegative timing bounds required')
    ui=1/(10*word_hz)
    return dict(error_s=sum(terms),sample_offset_ui=.5-sum(terms)/ui,
        aligned=word_phase_error==0,unit_interval_s=ui)


def continuous_framed_lane(word_hz,host_hz,mode,*,frames=256,depth=128,
                           prefill=64,phase_ui=0.,rate_error_ppm=0.,
                           direction="tx",service_pause_frames=0,
                           feedback_delay_frames=None,capture=False,
                           host_error_ppm=0.,host_phase_ui=0.):
    """Finite directional FIFO using actual framed codec and timestamped events.

    FPGA sends a fractional-rate word quota each frame, based on nominal lane
    rate. Consumer may have rate error. No feedback, CDC metastability or analog
    host timing is assumed; starvation/overflow stop the stream explicitly.
    """
    from stream_codec import slots,encode,Receiver
    from collections import deque
    if not (word_hz>0 and host_hz>0 and frames>0 and depth>0 and (direction=="rx" or 0<=prefill<=depth) and 0<=phase_ui<1):
        raise ValueError('Invalid stream geometry')
    actual=word_hz*(1+rate_error_ppm*1e-6)
    if actual<=0:raise ValueError('Invalid consumer clock')
    if not math.isfinite(host_error_ppm) or host_error_ppm<=-1e6 or not 0<=host_phase_ui<1:
        raise ValueError('Finite positive host frequency and bounded phase required')
    actual_host=host_hz*(1+host_error_ppm*1e-6)
    host_start=host_phase_ui/actual_host
    quota=slots(mode).count('wire');per_frame=64*word_hz/host_hz
    if per_frame>quota:raise ValueError('Host capacity exceeded')
    if direction not in ('tx','rx'):raise ValueError('Invalid direction')
    if type(service_pause_frames) is not int or service_pause_frames<0:
        raise ValueError('Nonnegative integer service pause required')
    if direction=='tx' and service_pause_frames:raise ValueError('RX-only service pause')
    if feedback_delay_frames is not None and (direction!='tx' or
            type(feedback_delay_frames) is not int or feedback_delay_frames<1):
        raise ValueError('TX feedback requires positive integer latency')
    if direction=='rx':
        # No preload in receive direction. Header quota snapshots occupancy;
        # later arrivals cannot be advertised retroactively in this frame.
        fifo=deque();produced=consumed=0;high=0;next_arrival=phase_ui/actual
        decoder=Receiver(mode);fault=None;now=0.;captures=[]
        def arrive(until):
            nonlocal next_arrival,produced,high,fault
            while next_arrival<=until:
                if len(fifo)==depth:fault='overflow';return
                fifo.append(produced%1024);produced+=1
                high=max(high,len(fifo));next_arrival+=1/actual
        for frame in range(frames):
            arrive(host_start+frame*64/actual_host)
            if fault:break
            count=0 if frame<service_pause_frames else min(quota,len(fifo))
            payload=list(fifo)[:count]
            for slot,word in enumerate(encode(mode,payload,[],frame%64)):
                now=host_start+(frame*64+slot)/actual_host
                arrive(now)
                if fault:break
                event=decoder.feed(word)
                if event and event[0]=='wire':
                    if not fifo or fifo.popleft()!=event[1] or event[1]!=consumed%1024:
                        raise AssertionError('Receive stream reordered or invented')
                    if capture:captures.append((now,event[1]))
                    consumed+=1
            if fault:break
        assert produced-consumed==len(fifo)
        return dict(direction=direction,fault=fault,produced=produced,consumed=consumed,
            pending_words=len(fifo),maximum_occupancy=high,depth=depth,
            frames_completed=frame if fault else frames,simulated_duration_s=now,
            rate_error_ppm=rate_error_ppm,service_pause_frames=service_pause_frames,
            host_error_ppm=host_error_ppm,host_phase_ui=host_phase_ui,
            **(dict(captures=captures) if capture else {}))
    fifo=deque(range(prefill));produced=prefill;consumed=0
    low=high=len(fifo);decoder=Receiver(mode);next_read=phase_ui/actual
    fault=None;observations=[];quota_phase=0.;captures=[]
    for frame in range(frames):
        observations.append(len(fifo))
        if feedback_delay_frames is None:
            count=math.floor((frame+1)*per_frame)-math.floor(frame*per_frame)
        else:
            # External controller receives a stale occupancy observation. It
            # cannot inspect the live FIFO or the actual consumer frequency.
            observed=observations[max(0,frame-feedback_delay_frames)]
            correction=(prefill-observed)/(4*(feedback_delay_frames+1))
            quota_phase+=max(0.,min(float(quota),per_frame+correction))
            count=math.floor(quota_phase);quota_phase-=count
        payload=[(produced+i)%1024 for i in range(count)];produced+=count
        for slot,word in enumerate(encode(mode,payload,[],frame%64)):
            now=host_start+(frame*64+slot)/actual_host
            # Conservative tie ordering: consumer precedes simultaneous write.
            while next_read<=now:
                if not fifo:fault='underflow';break
                value=fifo.popleft()
                if value!=consumed%1024:raise AssertionError('Stream reordered')
                if capture:captures.append((next_read,value))
                consumed+=1;next_read+=1/actual;low=min(low,len(fifo))
            if fault:break
            event=decoder.feed(word)
            if event and event[0]=='wire':
                if len(fifo)==depth:fault='overflow';break
                fifo.append(event[1]);high=max(high,len(fifo))
        if fault:break
    return dict(fault=fault,consumed=consumed,minimum_occupancy=low,
        maximum_occupancy=high,depth=depth,frames_completed=frame if fault else frames,
        simulated_duration_s=now,rate_error_ppm=rate_error_ppm,
        feedback_delay_frames=feedback_delay_frames,
        host_error_ppm=host_error_ppm,host_phase_ui=host_phase_ui,
        **(dict(captures=captures) if capture else {}))


def forwarded_pll_acquisition(word_hz, *, step_divisor=4, detuning_fraction=.01,
                              noise_rms_hz=0., qualification_cycles=32):
    """Three existing sampled PI/VCO models sharing a nominal reference.

    Initial phase and free-running frequency differ per die. Samples are taken
    after 4 us acquisition over the requested common qualification window.
    This reuses the existing bounded VCO model; gains are hypotheses, not devices.
    """
    from sampled_pll import SampledPLL
    lanes=[SampledPLL(reference_hz=word_hz,divider=10.,
        free_hz=10*word_hz*(1+detuning_fraction*sign),
        kvco_hz_per_v=200e6,bandwidth_hz=1e6,
        phase_cycles=phase,max_step_s=1/(word_hz*step_divisor))
        for sign,phase in ((-1.,-.2),(0.,.13),(1.,.35))]
    from oscillator_noise import FrequencyNoise
    for i,pll in enumerate(lanes):
        pll.set_noise(0.,FrequencyNoise.seeded(noise_rms_hz,seed=7531+i))
        pll.advance(4e-6)
    errors=[]
    for k in range(1,4*qualification_cycles+1):
        for pll in lanes:pll.advance(4e-6+k/(4*word_hz))
        errors.append([pll.error/word_hz for pll in lanes])
    peak=max(abs(e) for row in errors for e in row)
    skew=max(max(row)-min(row) for row in errors)
    timing=forwarded_clock_budget(word_hz,reference_error_s=10e-12,
        pll_error_s=peak,distribution_skew_s=25e-12)
    offset=timing['sample_offset_ui']
    eye=pad_eye([0,1]*128,bit_rate=10*word_hz,capacitance_f=2e-12,
        sample_offset_ui=offset,switch_tau_s=100e-12) if 0<offset<1 else dict(passes=False,minimum_signed_eye_v=None)
    return dict(peak_reference_error_s=peak,peak_inter_lane_skew_s=skew,
        noise_rms_hz=noise_rms_hz,pad_eye=eye,
        group_timing_ready=bool(peak<25e-12 and skew<50e-12 and eye['passes']),
        acquired_within_assumed_budget=peak<25e-12 and skew<50e-12,
        acquisition_s=4e-6,qualification_cycles=qualification_cycles,step_divisor=step_divisor,
        assumptions='Sampled ideal detector, PI filter, bounded VCO; declared finite-band noise, no device calibration, integer divider phase or PFD dead zone')


def observe_forwarded_payload(pll,words,*,lane_skew_s=0.,noise_rms_hz=20000.,
                              noise_seed=7531,capture=False):
    """Frozen-rail reduction of a configured PLL driving the real pad class.

    Receiver samples a nominal board-clock grid, never transmitter edge times.
    Board launch epoch and zero divider phase offset are declared assumptions.
    """
    import copy
    from oscillator_noise import FrequencyNoise
    from wired_blocks import CurrentSwitchChannel
    clock=copy.copy(pll);clock.supply_trajectory=None
    if clock.divider!=10 or clock.phase_offset!=0:raise ValueError('Known x10 launch epoch required')
    if not math.isfinite(lane_skew_s):raise ValueError('Finite lane skew required')
    clock.set_noise(clock.time,FrequencyNoise.seeded(noise_rms_hz,seed=noise_seed))
    acquired=clock.time+4e-6;clock.advance(acquired)
    for k in range(1,33):
        clock.advance(acquired+k/clock.reference_hz)
        clock.observe_lock()
    # Detector frequency-lock threshold can be stricter than jitter margin;
    # report it without using an invented lock override.
    locked=clock.locked
    start_phase=10*math.ceil(clock.reference_hz*clock.time+2)
    data=np.asarray(words)
    if data.ndim!=1 or not len(data) or data.dtype.kind not in 'iu' or np.any(data<0) or np.any(data>1023):
        raise ValueError('Opaque ten-bit words required')
    bits=((data[:,None]>>np.arange(10))&1).reshape(-1)
    rate=clock.reference_hz*10;events=[]
    for index,bit in enumerate(bits):
        edge=clock.edge_time(start_phase+index);clock.advance(edge)
        events.append((edge+lane_skew_s,0,int(bit)))
        events.append(((start_phase+index+.5)/rate,1,index))
    channel=CurrentSwitchChannel(rate);now=min(t for t,_,_ in events);drive=0.
    observed=[];margins=[];compliance=True
    for time,kind,value in sorted(events):
        channel.advance_state(drive,time-now);now=time
        if kind==0:drive=1. if value else -1.
        else:
            observed.append(int(channel.state>0))
            margins.append(channel.state*(1 if bits[value] else -1)*channel.volts_per_unit)
            compliance &= channel.pin_state()['current_compliance_valid']
    result=np.asarray(observed).reshape(-1,10)@(1<<np.arange(10))
    return dict(words=len(words),word_errors=int(np.count_nonzero(result!=data)),
        minimum_signed_sample_v=float(min(margins)),compliance_valid=bool(compliance),
        detector_lock_flag=bool(locked),lane_skew_s=lane_skew_s,
        receiver_clock='independent nominal forwarded grid',frozen_supply=True,
        **(dict(captures=[((start_phase+10*i+9.5)/rate,int(word))
            for i,word in enumerate(result)]) if capture else {}))
