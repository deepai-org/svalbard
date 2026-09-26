"""Reference-derived converter edges with bounded supply-dependent delay.

Candidate primitive, not installed in the full-chip scheduler. Voltage and slew
bounds must describe the same continuous forecast trajectory. Parameters are
hypotheses, not characterized GF180 buffer timing.
"""
import math
from dataclasses import dataclass
from scipy.optimize import brentq


@dataclass(frozen=True)
class EdgeProposal:
    index: int
    time: float


class ReferenceSampleClock:
    def __init__(self, reference_hz=40e6, origin=0., nominal_delay_s=1e-9,
                 delay_s_per_v=-.2e-9, nominal_v=3.3,
                 delay_bounds_s=(.25e-9,2e-9), jitter_bound_s=0., branch_delay_s=0.):
        values=(reference_hz,origin,nominal_delay_s,delay_s_per_v,nominal_v,
                *delay_bounds_s,jitter_bound_s,branch_delay_s)
        if not all(math.isfinite(v) for v in values) or reference_hz<=0:
            raise ValueError('Finite positive reference required')
        low,high=delay_bounds_s
        if not 0<low<=nominal_delay_s<=high<.25/reference_hz or jitter_bound_s<0:
            raise ValueError('Positive bounded delay below quarter reference period required')
        if not 0<=branch_delay_s<1/reference_hz:
            raise ValueError('Branch delay must be nonnegative and below one reference period')
        # Explicit nominal branch latency, separate from supply-dependent buffer
        # delay. This is a hypothetical delay element, not a characterized cell.
        self.branch_delay=branch_delay_s
        self.period=1/reference_hz;self.origin=origin
        self.delay=nominal_delay_s;self.sensitivity=delay_s_per_v;self.nominal_v=nominal_v
        self.bounds=(low,high);self.jitter_bound=jitter_bound_s
        self.present=True;self.index=None;self.divider=1
        self.last_time=-math.inf;self.proposal=None

    def arm(self, not_before, divider=1):
        if not self.present or self.index is not None:
            raise ValueError('Arming requires present reference and idle clock')
        if type(divider) is not int or divider not in (1,2,3,4,8) or not math.isfinite(not_before):
            raise ValueError('Finite guard and divide-by-one/two/three/four/eight required')
        guard=max(not_before,self.last_time)
        index=max(0,math.floor((guard-self.origin)/self.period)+1)
        index+=(-index)%divider
        self.index=index;self.divider=divider;self.proposal=None

    def stop(self):
        self.index=None;self.proposal=None

    def set_reference(self, present):
        if type(present) is not bool:raise ValueError('Boolean reference presence required')
        self.present=present
        if not present:self.stop()

    def forecast(self, voltage, *, maximum_slew_v_per_s, jitter_s=0., interval=None):
        # Invalidate an old forecast even when the new forecast fails.
        self.proposal=None
        if not self.present or self.index is None:
            raise ValueError('Clock must be armed with reference present')
        if not math.isfinite(maximum_slew_v_per_s) or maximum_slew_v_per_s<0:
            raise ValueError('Finite nonnegative rail slew bound required')
        if abs(self.sensitivity)*maximum_slew_v_per_s>=1:
            raise ValueError('Delay map is not guaranteed monotonic')
        if not math.isfinite(jitter_s) or abs(jitter_s)>self.jitter_bound:
            raise ValueError('Input timing noise exceeds declared bound')
        reference=self.origin+self.index*self.period+self.branch_delay
        low,high=self.bounds
        def residual(time):
            value=float(voltage(time))
            delay=self.delay+self.sensitivity*(value-self.nominal_v)+jitter_s
            if not math.isfinite(value) or not low<=delay<=high:
                raise ValueError('Buffer delay outside declared envelope')
            return time-reference-delay
        lo,hi=reference+low,reference+high
        full_hi=hi
        if interval is not None:
            begin,end=interval
            if not all(math.isfinite(t) for t in interval) or end<begin:
                raise ValueError('Finite increasing forecast interval required')
            lo=max(lo,begin);hi=min(hi,end)
            if hi<lo:
                if begin>full_hi:raise ValueError('Uncommitted edge predates forecast')
                return None
        a,b=residual(lo),residual(hi)
        if a>0:raise ValueError('Uncommitted edge predates forecast')
        if b<0:
            if interval is not None and hi<full_hi:return None
            raise ValueError('Edge not bracketed')
        when=brentq(residual,lo,hi,xtol=1e-20,rtol=1e-14) if lo!=hi else lo
        if when<=self.last_time:raise ValueError('Conversion edge would replay')
        self.proposal=EdgeProposal(self.index,when)
        return self.proposal

    def forecast_trajectory(self, trajectory, *, jitter_s=0.):
        """Consume the analog owner's piecewise-linear rail delta, without extrapolation.

        None means this interval ends before the edge; index/phase are retained.
        The continuous piecewise-linear representation supplies an exact slew
        bound for this approximation, not for the unextracted physical circuit.
        """
        self.proposal=None
        times=trajectory.times;deltas=trajectory.deltas
        slew=max((abs((b-a)/(y-x)) for x,y,a,b in
                  zip(times,times[1:],deltas,deltas[1:])),default=0.)
        return self.forecast(lambda t:self.nominal_v+trajectory.voltage(t),
            maximum_slew_v_per_s=slew,jitter_s=jitter_s,
            interval=(times[0],times[-1]))

    def consumed(self, time, remaining):
        """Commit the edge actually used by a converter, including its last one.

        Future deadlines stay unpublished until another bounded analog forecast.
        """
        if type(remaining) is not int or remaining<0:
            raise ValueError('Nonnegative integer remaining sample count required')
        self.commit(self.proposal,time)
        if not remaining:self.stop()
        return math.inf

    def commit(self, proposal, time):
        if proposal is not self.proposal or proposal is None or time!=proposal.time:
            raise ValueError('Only current forecast may commit at its edge')
        if not self.present or self.index!=proposal.index or time<=self.last_time:
            raise ValueError('Stale or noncausal conversion edge')
        self.last_time=time;self.index+=self.divider;self.proposal=None


def plan_converter_pair(not_before, rx_offset_s, *, now, divider=1,
                        reference_hz=40e6, origin=0., jitter_bound_s=0.):
    """Return fresh pending branches without changing any live clock state.

    not_before is a lower bound on the TX reference launch, not an exact
    absolute-time promise. Relative RX timing is preserved through complete
    reference cycles plus an explicit residual delay. Both source edges must
    still be in the future; large negative offsets reject rather than moving TX.
    Branches share a reference origin and divider cadence. Reference presence
    must still be owned and propagated by the eventual chip coordinator.
    """
    if not all(math.isfinite(v) for v in (not_before,rx_offset_s,now)):
        raise ValueError('Finite paired timing required')
    if not_before<=now:
        raise ValueError('Paired launch must be in the future')
    tx=ReferenceSampleClock(reference_hz=reference_hz,origin=origin,jitter_bound_s=jitter_bound_s)
    if type(divider) is not int or divider not in (1,2):
        raise ValueError('Divide-by-one/two required')
    # Ceiling keeps a requested lower bound; integer cycle decomposition keeps
    # negative offsets causal without introducing negative physical delay.
    index=max(0,math.ceil((not_before-origin)/tx.period))
    index+=(-index)%divider
    cycles=math.floor(rx_offset_s/tx.period)
    residual=rx_offset_s-cycles*tx.period
    rx=ReferenceSampleClock(reference_hz=reference_hz,origin=origin,
                            branch_delay_s=residual,jitter_bound_s=jitter_bound_s)
    rx_index=index+cycles
    if rx_index<0 or origin+rx_index*tx.period<=now:
        raise ValueError('RX offset requires a past reference edge')
    tx.index=index;rx.index=rx_index
    tx.divider=rx.divider=divider
    return tx,rx


def refine_converter_edge(clock, forecast, *, step_s=.5e-9, tolerance_s=1e-15,
                          maximum_refinements=10):
    """Resolve one pending edge against a freshly shortened analog forecast.

    forecast(end, step) must return a PLL-domain trajectory without mutating
    live state. No clock edge commits here. Both interpolation and endpoint
    consistency are checked; callers must still install/consume atomically.
    """
    if (not math.isfinite(step_s) or not math.isfinite(tolerance_s)
            or min(step_s,tolerance_s)<=0 or type(maximum_refinements) is not int
            or maximum_refinements<1):
        raise ValueError('Positive finite refinement controls required')
    if clock.index is None or not clock.present:
        raise ValueError('Present armed reference required')
    reference=clock.origin+clock.index*clock.period+clock.branch_delay
    upper=reference+clock.bounds[1]
    for refinement in range(maximum_refinements):
        trajectory=forecast(upper,step_s)
        edge=clock.forecast_trajectory(trajectory)
        if edge is None:raise ValueError('Forecast does not bracket converter edge')
        shortened=forecast(edge.time,step_s)
        voltage=clock.nominal_v+shortened.voltage(edge.time)
        residual=edge.time-reference-clock.delay-clock.sensitivity*(voltage-clock.nominal_v)
        # A second resolution check guards an accidentally small endpoint
        # residual from a coarse interpolation of a rapidly changing rail.
        finer=forecast(upper,step_s/2)
        refined=clock.forecast_trajectory(finer)
        if refined is None:raise ValueError('Refined forecast lost converter edge')
        if abs(residual)<=tolerance_s and abs(refined.time-edge.time)<=tolerance_s:
            final=forecast(refined.time,step_s/2)
            value=clock.nominal_v+final.voltage(refined.time)
            error=refined.time-reference-clock.delay-clock.sensitivity*(value-clock.nominal_v)
            if abs(error)<=tolerance_s:
                return refined,dict(step_s=step_s/2,refinements=refinement,
                    endpoint_residual_s=error,edge_refinement_s=refined.time-edge.time)
        step_s/=2
    clock.proposal=None
    raise ValueError('Converter edge and analog forecast did not converge')


def forecast_converter_boundary(clocks, forecast_voltage, *, start, end,
                                maximum_slew_v_per_s, reference_jitter=None):
    """Find pending branch edges without crossing the next external event.

    forecast_voltage(t) must independently forecast the same uncommitted analog
    state to t and return its absolute PLL rail voltage. Endpoint solves avoid
    interpolating across a host/control discontinuity. Returned later proposals
    are discarded: the first conversion changes analog loading.
    """
    clocks=tuple(clocks)
    # Any attempted reforecast invalidates old proposals, including rejected
    # horizons: no stale edge may survive a failed scheduler update.
    for clock in clocks:clock.proposal=None
    if not all(math.isfinite(t) for t in (start,end)) or end<start:
        raise ValueError('Finite ordered coordinator interval required')
    if len({id(c) for c in clocks})!=len(clocks):
        raise ValueError('Each converter branch must have a distinct clock')
    cache={};jitter_cache={}
    def voltage(time):
        if not start<=time<=end:raise ValueError('Forecast crossed event boundary')
        if time not in cache:cache[time]=forecast_voltage(time)
        return cache[time]
    proposals=[]
    try:
        for clock in clocks:
            if clock.index is None:continue
            # Evaluate timing noise once for each shared physical reference edge.
            # The callback must be deterministic across repeated forecasts.
            key=(clock.origin,clock.period,clock.index)
            if key not in jitter_cache:
                jitter_cache[key]=0. if reference_jitter is None else reference_jitter(clock.index)
            proposal=clock.forecast(voltage,jitter_s=jitter_cache[key],
                maximum_slew_v_per_s=maximum_slew_v_per_s,interval=(start,end))
            if proposal is not None:proposals.append((clock,proposal))
        boundary=min((p.time for _,p in proposals),default=end)
        due=[]
        for clock,proposal in proposals:
            if proposal.time==boundary:due.append((clock,proposal))
            else:clock.proposal=None
        return boundary,tuple(due)
    except Exception:
        for clock in clocks:clock.proposal=None
        raise


def controls():
    """Analytic timing and state controls; no full-chip integration claim."""
    count=0;maximum_error=0.
    for divider in (1,2):
        c=ReferenceSampleClock();c.arm(0.,divider)
        for i in range(64):
            edge=c.forecast(lambda t:3.3,maximum_slew_v_per_s=0.)
            expected=(i+1)*divider/40e6+1e-9
            maximum_error=max(maximum_error,abs(edge.time-expected))
            assert abs(edge.time-expected)<1e-18
            c.commit(edge,edge.time);count+=1
        last=c.last_time;c.stop();c.arm(last,divider)
        assert c.index%divider==0
        # Analytic affine supply root; anchored around this next reference edge.
        r=c.origin+c.index*c.period;slope=1e7
        edge=c.forecast(lambda t:3.3+slope*(t-r),maximum_slew_v_per_s=slope)
        expected=r+c.delay/(1-c.sensitivity*slope)
        assert abs(edge.time-expected)<1e-18
        old=edge
        edge=c.forecast(lambda t:3.2,maximum_slew_v_per_s=0.)
        try:c.commit(old,old.time)
        except ValueError:pass
        else:raise AssertionError('Stale forecast committed')
        assert edge.time>r+c.delay
        c.set_reference(False)
        try:c.commit(edge,edge.time)
        except ValueError:pass
        else:raise AssertionError('Reference loss retained edge')
        c.set_reference(True);assert c.index is None
    # Two branches retain the same reference divider phase but have distinct
    # nominal propagation delays. Rail sensitivity still acts at each output edge.
    for divider in (1,2):
        tx=ReferenceSampleClock();rx=ReferenceSampleClock(branch_delay_s=10e-9)
        tx.arm(0.,divider);rx.arm(0.,divider)
        for _ in range(16):
            te=tx.forecast(lambda t:3.3,maximum_slew_v_per_s=0.)
            re=rx.forecast(lambda t:3.3,maximum_slew_v_per_s=0.)
            assert te.index==re.index and abs(re.time-te.time-10e-9)<1e-18
            tx.commit(te,te.time);rx.commit(re,re.time)
        rx.stop();rx.arm(rx.last_time,divider)
        assert rx.index%divider==0
    for delay in (-1e-12,25e-9,float('nan')):
        try:ReferenceSampleClock(branch_delay_s=delay)
        except ValueError:pass
        else:raise AssertionError('Unsupported branch delay accepted')
    paired=0
    for divider in (1,2):
        for offset in (-60e-9,-25e-9,-10e-9,0.,10e-9,25e-9,60e-9):
            tx,rx=plan_converter_pair(200e-9,offset,now=0.,divider=divider)
            for _ in range(4):
                te=tx.forecast(lambda t:3.3,maximum_slew_v_per_s=0.)
                re=rx.forecast(lambda t:3.3,maximum_slew_v_per_s=0.)
                assert abs(re.time-te.time-offset)<1e-18
                tx.commit(te,te.time);rx.commit(re,re.time);paired+=1
    for kwargs in (dict(not_before=25e-9,rx_offset_s=-50e-9,now=0.),
                   dict(not_before=0.,rx_offset_s=0.,now=0.),
                   dict(not_before=25e-9,rx_offset_s=0.,now=0.,divider=3)):
        try:plan_converter_pair(**kwargs)
        except ValueError:pass
        else:raise AssertionError('Invalid paired launch accepted')
    from autonomous_pll import SupplyTrajectory
    c=ReferenceSampleClock();c.arm(0.)
    def affine_forecast(end,step):
        # Exact affine trace, with a start before the bracket.
        return SupplyTrajectory((25e-9,end),(0.,-1e8*(end-25e-9)))
    edge,metrics=refine_converter_edge(c,affine_forecast)
    expected=(26e-9-.02*25e-9)/.98
    assert abs(edge.time-expected)<1e-18 and abs(metrics['endpoint_residual_s'])<1e-18
    c.commit(edge,edge.time)
    jittered=ReferenceSampleClock(jitter_bound_s=100e-12);jittered.arm(0.)
    for i in range(32):
        jitter=(0.,100e-12,0.,-100e-12)[i%4]
        edge=jittered.forecast(lambda t:3.3,maximum_slew_v_per_s=0.,jitter_s=jitter)
        assert abs(edge.time-((i+1)/40e6+1e-9+jitter))<1e-18
        jittered.commit(edge,edge.time)
    c=ReferenceSampleClock();c.arm(0.)
    for fn in (lambda:c.forecast(lambda t:0.,maximum_slew_v_per_s=1e10),
               lambda:c.forecast(lambda t:100.,maximum_slew_v_per_s=0.),
               lambda:c.forecast(lambda t:3.3,maximum_slew_v_per_s=0.,jitter_s=1e-12)):
        try:fn()
        except ValueError:pass
        else:raise AssertionError('Invalid envelope accepted')
    from autonomous_pll import SupplyTrajectory
    c=ReferenceSampleClock();c.arm(0.)
    early=SupplyTrajectory((0.,25.5e-9),(0.,0.))
    assert c.forecast_trajectory(early) is None and c.index==1
    on_time=SupplyTrajectory((25.5e-9,26.5e-9),(0.,-.1))
    edge=c.forecast_trajectory(on_time)
    # delta=-1e8*(t-25.5 ns); solve affine equation independently.
    expected=(26e-9-.02*25.5e-9)/.98
    assert abs(edge.time-expected)<1e-18
    assert c.index==1 and c.last_time==-math.inf
    c.commit(edge,edge.time)
    try:c.forecast_trajectory(SupplyTrajectory((60e-9,61e-9),(0.,0.)))
    except ValueError:pass
    else:raise AssertionError('Missed conversion edge was skipped silently')
    # Bounded coordinator: host-event horizon, successive branch edges, and
    # simultaneous independent branches. No callback may look past its horizon.
    tx,rx=plan_converter_pair(25e-9,10e-9,now=0.)
    calls=[]
    def rail(t):calls.append(t);return 3.3
    boundary,due=forecast_converter_boundary((tx,rx),rail,start=0.,end=25.5e-9,
        maximum_slew_v_per_s=0.)
    assert boundary==25.5e-9 and not due and max(calls)<=25.5e-9
    boundary,due=forecast_converter_boundary((tx,rx),rail,start=25.5e-9,end=40e-9,
        maximum_slew_v_per_s=0.)
    assert len(due)==1 and due[0][0] is tx and rx.proposal is None
    tx.consumed(boundary,1)
    next_boundary,due=forecast_converter_boundary((tx,rx),rail,start=boundary,end=40e-9,
        maximum_slew_v_per_s=0.)
    assert len(due)==1 and due[0][0] is rx and abs(next_boundary-boundary-10e-9)<1e-18
    rx.consumed(next_boundary,0)
    tx,rx=plan_converter_pair(25e-9,0.,now=0.)
    boundary,due=forecast_converter_boundary((tx,rx),rail,start=0.,end=40e-9,
        maximum_slew_v_per_s=0.)
    assert len(due)==2
    for clock,proposal in due:clock.consumed(boundary,0)
    tx,rx=plan_converter_pair(25e-9,0.,now=0.)
    _,old=forecast_converter_boundary((tx,rx),lambda t:3.3,start=0.,end=40e-9,
        maximum_slew_v_per_s=0.)
    boundary,fresh=forecast_converter_boundary((tx,rx),lambda t:3.2,start=25.5e-9,end=40e-9,
        maximum_slew_v_per_s=0.)
    assert len(fresh)==2 and abs(boundary-old[0][1].time-20e-12)<1e-18
    for branch,proposal in old:
        try:branch.commit(proposal,proposal.time)
        except ValueError:pass
        else:raise AssertionError('Pre-disturbance proposal survived new rail forecast')
    try:forecast_converter_boundary((tx,rx),rail,start=40e-9,end=0.,maximum_slew_v_per_s=0.)
    except ValueError:pass
    else:raise AssertionError('Reversed event horizon accepted')
    assert tx.proposal is None and rx.proposal is None
    _,due=forecast_converter_boundary((tx,rx),rail,start=0.,end=40e-9,maximum_slew_v_per_s=0.)
    for branch,_ in due:branch.set_reference(False)
    for branch,proposal in due:
        try:branch.commit(proposal,proposal.time)
        except ValueError:pass
        else:raise AssertionError('Lost reference retained paired conversion')
        branch.set_reference(True)
        assert branch.index is None
    tx,rx=plan_converter_pair(25e-9,10e-9,now=0.,jitter_bound_s=100e-12)
    noise_calls=[]
    def timing_error(index):noise_calls.append(index);return 100e-12
    when,due=forecast_converter_boundary((tx,rx),rail,start=0.,end=40e-9,
        maximum_slew_v_per_s=0.,reference_jitter=timing_error)
    assert noise_calls==[1] and abs(when-26.1e-9)<1e-18
    tx.consumed(when,0)
    when,due=forecast_converter_boundary((rx,),rail,start=when,end=40e-9,
        maximum_slew_v_per_s=0.,reference_jitter=timing_error)
    assert abs(when-36.1e-9)<1e-18
    try:forecast_converter_boundary((rx,),rail,start=0.,end=40e-9,
        maximum_slew_v_per_s=0.,reference_jitter=lambda index:101e-12)
    except ValueError:pass
    else:raise AssertionError('Unbounded reference disturbance accepted')
    assert rx.proposal is None
    # Exercise the actual converter consumption and cancellation paths. These
    # use the small lifecycle composition, not the canonical analog forecast.
    from rf_return_lifecycle import ReturnChip
    for sample_count in (1,2):
        chip=ReturnChip();chip.configure(0,0.);chip.advance(chip.acquisition_s)
        clock=ReferenceSampleClock();clock.arm(chip.time)
        edge=clock.forecast(lambda t:3.3,maximum_slew_v_per_s=0.)
        chip.capture(sample_count,edge.time);chip.adc_clock=clock
        chip.advance(edge.time)
        assert chip.adc_sampled==1 and clock.last_time==edge.time
        assert math.isinf(chip.next_adc) and clock.proposal is None
        if sample_count==1:assert clock.index is None
        else:
            assert clock.index is not None
            chip.quiesce(chip.time,'clock lifecycle control')
            assert clock.index is None and clock.proposal is None
    return dict(shared_reference_jitter=True,paired_disturbance_and_reference_loss=True,rejected_horizon_invalidates_proposals=True,bounded_pair_coordinator=True,converter_lifecycle_final_and_cancel=True,shortened_forecast_affine_control=True,signed_offset_pairs=paired,invalid_pair_plans_rejected=True,branch_delay_pairs=32,invalid_branch_delays_rejected=True,trajectory_horizon_and_affine_root=True,missed_edge_rejected=True,
                committed_nominal_edges=count,maximum_nominal_error_s=maximum_error,
                analytic_ramp=True,bounded_jitter_edges=32,stale_forecast_rejected=True,reference_loss_cancels=True,
                invalid_envelopes_rejected=True,full_chip_integration=False)


def payload_controls():
    """Reduced connected converter/transport run on an analytic supply trace.

    Uses real inherited lifecycle methods; omits detailed RF acquisition and
    nonlinear rail/RF feedback. No warm-start state is promoted to qualification.
    """
    from rf_return_lifecycle import ReturnChip
    from chip_model import encode,encode_iq
    from burst_codec import BurstEncoder
    rows=[]
    for mode,interrupted in ((0,False),(1,False),(0,True),(1,True)):
        chip=ReturnChip(watchdog_s=20e-6)
        chip.configure(mode,0.);chip.advance(chip.acquisition_s)
        begin=chip.time;start=begin+2e-6;count=32
        rate=250e6 if mode==0 else 312.5e6
        chip.descriptor(count);encoder=BurstEncoder(2*chip.bits,count);words=[]
        for i in range(count):words+=encoder.push(encode_iq(complex((i%7-3)/16,.1),chip.bits))
        words+=encoder.finish()
        chip.schedule(count,start);chip.capture(count,start+10e-9)
        from stream_codec import slots
        quota=slots(mode).count('iq');frames=[]
        for sequence,offset in enumerate(range(0,len(words),quota)):
            frames+=encode(mode,[],words[offset:offset+quota],sequence)
        for i,word in enumerate(frames):
            chip.feed(word,chip.epoch,begin+(i+1)/rate)
        chip.finish_burst()
        tx,rx=plan_converter_pair(start,10e-9,now=chip.time,divider=mode+1,jitter_bound_s=100e-12)
        chip.sample_clock=tx;chip.adc_clock=rx
        chip.next_sample=chip.next_adc=math.inf
        end=start+count*(mode+1)/40e6+2e-6
        loss_at=start+8*(mode+1)/40e6+15e-9 if interrupted else math.inf
        observed={'tx':[],'rx':[]};iterations=0
        def voltage(t):return 3.3-.05*math.sin(2*math.pi*1e6*t)
        while chip.time<end:
            horizon=min(end,loss_at,chip.next_return,
                chip.dac_pending[0][0] if chip.dac_pending else math.inf,
                chip.adc_pending[0][0] if chip.adc_pending else math.inf)
            if horizon<=chip.time:raise AssertionError('Reduced coordinator stalled')
            active=[clock for clock in (tx,rx) if clock.index is not None]
            boundary,due=forecast_converter_boundary(active,voltage,start=chip.time,end=horizon,
                maximum_slew_v_per_s=.05*2*math.pi*1e6,
                reference_jitter=lambda index:100e-12*math.sin(index*math.pi/4))
            for clock,proposal in due:
                if clock is tx:chip.next_sample=proposal.time;observed['tx'].append(proposal.time)
                else:chip.next_adc=proposal.time;observed['rx'].append(proposal.time)
            chip.advance(boundary);iterations+=1
            assert iterations<10000 and chip.state=='active'
            if boundary==loss_at:
                before=(len(chip.played),chip.adc_sampled,chip.return_ticks)
                chip.set_reference(False,chip.time)
                assert chip.state=='draining' and tx.index is None and rx.index is None
                assert tx.proposal is None and rx.proposal is None
                chip.advance(end)
                assert before==(len(chip.played),chip.adc_sampled,chip.return_ticks)
                assert chip.remaining==chip.adc_left==0 and not chip.dac_pending and not chip.adc_pending
                assert chip.tx.accounting()['discarded']==count-chip.tx.consumed
                chip.acknowledge_host_abort(chip.epoch,chip.time)
                chip.acknowledge_drain(chip.epoch,chip.time)
                assert chip.state=='reset'
                break
        if not interrupted:
            chip.host_decoder.finish()
            assert len(chip.played)==chip.adc_sampled==len(chip.host_samples)==count
            assert chip.host_samples==chip.adc_words and chip.remaining==chip.adc_left==0
        assert tx.index is None and rx.index is None
        chip.dac_accounting();chip.adc_accounting()
        nominal=[observed['tx'][0]+i*(mode+1)/40e6 for i in range(len(observed['tx']))]
        timing=max(abs(a-b) for a,b in zip(observed['tx'],nominal))
        assert timing>1e-12  # The imposed rail variation actually reaches timing.
        rows.append(dict(mode=mode,reference_jitter_bound_s=100e-12,reference_loss=interrupted,played=len(chip.played),captured=chip.adc_sampled,returned=len(chip.host_samples),
            maximum_tx_nominal_grid_error_s=timing,coordinator_intervals=iterations))
    return dict(cases=rows,full_chip_closure=False,
        scope='Reduced converter, sample-clock and framed-return lifecycle with prescribed sinusoidal rail and shared bounded reference jitter; no autonomous RF acquisition or coupled power proof.')


def coupled_controls(rail_step_s=7.8125e-12):
    """Forecast/commit consistency on canonical inactive-RF rails, without converters."""
    import sys
    from pathlib import Path
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'verification'))
    from full_chip_model import make_chip
    from driver_pll_feedback import forecast_trajectory_feedback
    rows=[]
    for switching in (False,True):
        for divider in (1,2):
            chip=make_chip();clock=ReferenceSampleClock();clock.arm(0.,divider)
            maximum_residual=0.;times=[]
            for index in range(4):
                if switching:
                    chip.advance(clock.origin+clock.index*clock.period+.5e-9)
                    chip.emitted_return_word(1023 if index%2==0 else 0,chip.time)
                end=clock.origin+clock.index*clock.period+clock.bounds[1]
                chip.configure_analog_loads()
                owner=chip.analog_owner
                start=chip.time;old_voltage=owner.domains.voltage.copy()
                candidate,_,_=forecast_trajectory_feedback(owner,chip.rf_pll,end,
                    [(0j,0j)],chip.rf_hz_per_v,rail_step_s,inactive_rf=True)
                assert chip.time==owner.time==chip.rf_pll.time==start
                assert (owner.domains.voltage==old_voltage).all()
                edge=clock.forecast_trajectory(candidate.domain_trajectories['PLL'])
                assert edge is not None
                chip.advance(edge.time)
                domain=chip.analog_owner.domains
                voltage=float(domain.voltage[list(domain.names).index('PLL')])
                reference=clock.origin+edge.index*clock.period
                residual=edge.time-reference-clock.delay-clock.sensitivity*(voltage-clock.nominal_v)
                maximum_residual=max(maximum_residual,abs(residual))
                assert abs(residual)<1e-15, residual
                clock.commit(edge,chip.time);times.append(chip.time)
                assert clock.last_time==chip.time==chip.analog_owner.time==chip.rf_pll.time
            rows.append(dict(host_switching=switching,divider=divider,edges_s=times,maximum_committed_residual_s=maximum_residual))
    return dict(rail_step_s=rail_step_s,cases=rows,scope='Inactive RF, quiet/toggling canonical host pads, no ADC/DAC activity; forecast/advance/clock-commit consistency only.',
                full_chip_integration=False,physical_qualification=False)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--coupled-controls',action='store_true')
    parser.add_argument('--payload-controls',action='store_true')
    parser.add_argument('--rail-step-ns',type=float,default=.0078125)
    args=parser.parse_args()
    print(payload_controls() if args.payload_controls else coupled_controls(args.rail_step_ns*1e-9) if args.coupled_controls else controls())
