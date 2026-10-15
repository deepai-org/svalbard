"""Reference-synchronous group launch requirements, not PLL/skew qualification."""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Compensation:
    words: int
    bits: int
    board_fraction_ui: float


def compensate(delays_ui):
    """Align measured fixed latencies; fractional correction is explicitly external."""
    if not delays_ui or any(not math.isfinite(d) or d<0 for d in delays_ui):
        raise ValueError('finite nonnegative calibrated delays required')
    target=math.ceil(max(delays_ui))
    result=[]
    for delay in delays_ui:
        needed=target-delay
        coarse=math.floor(needed)
        if coarse>39:
            raise ValueError('calibrated lane spread exceeds local delay allocation')
        result.append(Compensation(coarse//10,coarse%10,needed-coarse))
    return result


@dataclass
class Lane:
    epoch: int
    launch_count: int = 16
    armed: bool = False
    captured_edge: int | None = None

    def arm(self, *, pll_locked, phase_qualified, prefilled):
        if not (pll_locked and phase_qualified and prefilled):
            raise ValueError('lane cannot arm before clock/phase/payload readiness')
        if not 4<=self.launch_count<=65535:
            raise ValueError('invalid launch count')
        self.armed=True
        self.captured_edge=None

    def marker(self, reference_edge, *, cs_inactive, capture_window_valid):
        if not self.armed or self.captured_edge is not None:
            raise ValueError('marker without fresh arm')
        if not cs_inactive or not capture_window_valid:
            raise ValueError('marker edge not qualified')
        if type(reference_edge) is not int or reference_edge<0:
            raise ValueError('invalid reference count')
        self.captured_edge=reference_edge


def launch_group(lanes, *, at_reference_edge, epoch, clocks_valid,
                 payloads_ready, calibrated_delays_ui, compensation,
                 uncertainty_ui, allowed_skew_ui=.25):
    """Reject late or inconsistent group launches instead of shifting the deadline."""
    count=len(lanes)
    if not count or any(len(v)!=count for v in (clocks_valid,payloads_ready,
                    calibrated_delays_ui,compensation,uncertainty_ui)):
        raise ValueError('one readiness/calibration entry per lane required')
    if not all(clocks_valid) or not all(payloads_ready):
        raise ValueError('group fault or underrun')
    if any(not l.armed or l.epoch!=epoch or l.captured_edge is None for l in lanes):
        raise ValueError('group epoch or arm mismatch')
    if len({l.captured_edge for l in lanes})!=1:
        raise ValueError('lanes captured different reference edges')
    if any(at_reference_edge != l.captured_edge+l.launch_count for l in lanes):
        raise ValueError('late or inconsistent launch count')
    arrivals=[]
    for delay,c,u in zip(calibrated_delays_ui,compensation,uncertainty_ui):
        if not (0<=c.words<=3 and 0<=c.bits<=9 and 0<=c.board_fraction_ui<1):
            raise ValueError('delay setting out of bounds')
        if not math.isfinite(delay) or not math.isfinite(u) or delay<0 or u<0:
            raise ValueError('invalid calibrated uncertainty')
        arrivals.append(delay+c.words*10+c.bits+c.board_fraction_ui)
    span=max(t+u for t,u in zip(arrivals,uncertainty_ui))-min(t-u for t,u in zip(arrivals,uncertainty_ui))
    if span>allowed_skew_ui+1e-12:
        raise ValueError('connector skew budget not met')
    for lane in lanes:lane.armed=False
    return arrivals


class ConfiguredLaneClock:
    """Retained sampled PLL and divider resolved from the shared configuration.

    Uses local phase-detector observations, not transmitted data or scoreboard
    timing. The shared reference-input factory can supply loaded input edges; omitting
    that provider is an explicit ideal-reference fixture.
    """
    def __init__(self, configuration, *, initial_frequency_error_ppm=10000., initial_phase_cycles=.13, reference_edge_provider=None):
        if configuration.engine!='wire' or configuration.clock_source!='forwarded_word':
            raise ValueError('Forwarded wired configuration required')
        from sampled_pll import SampledPLL
        self.configuration=configuration
        a=configuration.design.architecture
        pll=a['blocks']['wirepll']['parameters']
        q=a['blocks']['clocktree']['parameters']['alignment_qualification']
        pi=a['model_assumptions']['forwarded_clock_pi']['parameters']
        self.output_divider=configuration.wire_output_divider
        self.nominal_vco_hz=configuration.wire_clock_hz*self.output_divider
        self.phase_limit_ui=q['maximum_phase_error_ui']
        self.required_cycles=q['stable_reference_cycles']
        self.settle_s=pll['settle_s']
        self.vco_limits=tuple(pll['physical_vco_qualification_hz'])
        self.pll=SampledPLL(reference_hz=configuration.reference_hz,
            divider=self.nominal_vco_hz/configuration.reference_hz,
            free_hz=self.nominal_vco_hz*(1+initial_frequency_error_ppm*1e-6),
            kvco_hz_per_v=pll['vco_gain_hz_per_v'],bandwidth_hz=pi['bandwidth_hz'],
            damping=pi['damping'],rail_v=pi['control_rail_v'],phase_cycles=initial_phase_cycles,
            max_step_s=1/(configuration.reference_hz*pi['steps_per_reference']),
            reference_edge_provider=reference_edge_provider)
        self.reference_index=0;self.stable_cycles=0;self.ready=False
        self.source_epoch=0;self.source_since=0.;self.supply_valid=True

    def advance(self,time):
        if not math.isfinite(time) or time<self.pll.time:raise ValueError('Monotonic clock time required')
        ref=self.configuration.reference_hz
        while self.pll.next_detector<=time:
            self.reference_index+=1
            try:self.pll.advance(self.pll.next_detector)
            except ValueError:
                self.ready=False;self.stable_cycles=0
                raise
            error_ui=abs(self.pll.detector_error)*self.configuration.wire_clock_hz/ref
            good=(self.pll.present and self.supply_valid and error_ui<=self.phase_limit_ui and
                  self.vco_limits[0]<=self.pll.frequency_hz<=self.vco_limits[1])
            self.stable_cycles=self.stable_cycles+1 if good else 0
            self.ready=(good and self.stable_cycles>=self.required_cycles and
                        self.pll.time-self.source_since>=self.settle_s)
        self.pll.advance(time)
        return self.ready

    def set_source(self,present,time):
        self.advance(time)
        if bool(present)!=self.pll.present:
            self.pll.set_reference(present,time)
            self.source_epoch+=1;self.source_since=time
            self.stable_cycles=0;self.ready=False

    def set_supply_valid(self,valid,time):
        self.advance(time)
        if bool(valid)!=self.supply_valid:
            self.supply_valid=bool(valid);self.stable_cycles=0;self.ready=False
            self.source_since=time

    @property
    def output_hz(self):return self.pll.frequency_hz/self.output_divider

    @property
    def output_phase_cycles(self):return self.pll.output_phase_cycles/self.output_divider


class ConfiguredVideoStream:
    """Framed FPGA input and finite FIFO consumed by the retained synthesized clock.

    Words are opaque, FPGA-encoded symbols. This models clock/transport/epoch
    continuity; connector pad settling and video encoding are separate checks.
    """
    def __init__(self,clock):
        from collections import deque
        from stream_codec import Receiver
        self.clock=clock;self.configuration=clock.configuration
        a=self.configuration.design.architecture
        self.capacity=a['resource_policy']['memory_bits']['ingress']//10
        self.service=a['model_assumptions']['forwarded_stream_service']['parameters']
        self.fifo=deque();self.decoder=Receiver(1,owner='wire')
        self.epoch=0;self.running=False;self.fault=None;self.high_water=0
        self.next_phase=None;self.emitted=[];self.flushes=[];self.host_words=0

    def _fail(self,reason):
        self.running=False;self.next_phase=None;self.fault=reason

    def advance(self,time):
        if time<self.clock.pll.time:raise ValueError('Monotonic stream time required')
        while self.running:
            target=self.next_phase*self.clock.output_divider
            when=self.clock.pll.edge_time(target)
            if when>time:break
            if not self.clock.advance(when):self._fail('clock_not_ready');break
            if not self.fifo or self.fifo[0][0]>when:
                self._fail('underflow');break
            _,word=self.fifo.popleft()
            self.emitted.append((when,self.epoch,word))
            self.next_phase+=10
        self.clock.advance(time)
        if self.running and not self.clock.ready:self._fail('clock_not_ready')

    def receive_host_word(self,word,time,epoch):
        if epoch!=self.epoch:raise ValueError('Stale stream epoch')
        self.advance(time)
        if self.fault is not None:raise ValueError('Stream fault requires explicit recovery')
        try:event=self.decoder.feed(word)
        except ValueError:
            self._fail('host_frame');raise
        self.host_words+=1
        if event and event[0]=='wire':
            if len(self.fifo)>=self.capacity:
                self._fail('overflow');raise ValueError('Video ingress overflow')
            delay=(self.service['host_cdc_cycles']/self.configuration.h2d_clock_hz+
                   self.service['consumer_cdc_cycles']/(self.configuration.line_rate_bps/10))
            self.fifo.append((time+delay,event[1]));self.high_water=max(self.high_water,len(self.fifo))

    def launch(self,reference_count,epoch):
        if epoch!=self.epoch or self.fault is not None or self.running:
            raise ValueError('Invalid video launch state or epoch')
        provider=self.clock.pll.reference_edge_provider
        when=(reference_count/self.configuration.reference_hz if provider is None else provider(reference_count))
        if when<self.clock.pll.time:raise ValueError('Late video launch marker')
        self.advance(when)
        ready_words=sum(t<=when for t,_ in self.fifo)
        if not self.clock.ready or ready_words<self.service['minimum_prefill_words']:
            raise ValueError('Video launch requires qualified clock and prefill')
        self.next_phase=math.ceil(self.clock.output_phase_cycles)+self.service['launch_pipeline_ui']
        self.running=True
        return when

    def source_presence(self,present,time):
        self.advance(time)
        self.clock.set_source(present,time)
        if not present:self._fail('reference_lost')

    def stop(self,time):
        self.advance(time)
        self.running=False;self.next_phase=None

    def recover(self,time,new_epoch):
        """Explicit stopped flush/reset command; PLL and its input are retained."""
        self.advance(time)
        if self.running or new_epoch!=self.epoch+1:
            raise ValueError('Recovery requires stopped stream and next epoch')
        self.flushes.append(dict(time_s=time,discarded_words=len(self.fifo),old_epoch=self.epoch))
        self.fifo.clear();self.decoder.reset();self.epoch=new_epoch;self.fault=None
