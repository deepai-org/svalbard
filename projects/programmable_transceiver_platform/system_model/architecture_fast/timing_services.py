"""Selected timing contracts for warm retuning and FPGA-owned gain feedback.

Readiness observations and settling bounds are supplied, not analog predictions.
The state machine cannot convert a late or missing observation into readiness.
"""
import math


class WarmHop:
    def __init__(self, epoch, deadline_s=50e-6):
        if not math.isfinite(deadline_s) or deadline_s<=0:raise ValueError('deadline')
        self.epoch=epoch;self.deadline=deadline_s;self.state='active';self.time=0.
        self.ready=False;self.output=False

    @classmethod
    def from_configuration(cls, configuration, epoch):
        if configuration.engine!='rf' or configuration.host_clock_source!='h2d_divided':
            raise ValueError('Warm hop requires the stable shared RF host configuration')
        result=cls(epoch,configuration.design.architecture['warm_hop_service']['maximum_gap_s'])
        result.configuration=configuration
        result.next_configuration=None
        return result

    def begin_configuration(self, next_configuration, *, context_loaded, muted, queues_discarded):
        current=self.configuration
        if (next_configuration.design.fingerprint!=current.design.fingerprint or
                next_configuration.engine!='rf' or
                next_configuration.host_clock_source!='h2d_divided' or
                next_configuration.direction!=current.direction or
                next_configuration.host_word_hz!=current.host_word_hz or
                next_configuration.h2d_word_hz!=current.h2d_word_hz):
            raise ValueError('Hop must preserve shared design, direction and host clocks')
        self.begin(host_stable=True,context_loaded=context_loaded,muted=muted,queues_discarded=queues_discarded)
        self.next_configuration=next_configuration

    def begin(self, *, host_stable, context_loaded, muted, queues_discarded):
        if self.state!='active' or not all((host_stable,context_loaded,muted,queues_discarded)):
            raise ValueError('hop preconditions')
        self.epoch+=1;self.state='retuning';self.output=False;self.ready=False;self.time=0.

    def observe(self,time,*,host_ok=True,supply_ok=True,source_qualified=False,
                samples_flushed=False,gain_settled=False,epoch_ack=False,prefilled=False):
        if not math.isfinite(time) or time<self.time:raise ValueError('monotonic time')
        self.time=time
        if self.state=='fault':return False
        if not host_ok or not supply_ok or time>self.deadline:
            self.state='fault';self.ready=False;self.output=False;return False
        if self.state=='retuning' and source_qualified:
            self.state='settling'
            return False  # Cannot skip source->converter boundary on one observation.
        if self.state=='settling' and source_qualified and all((samples_flushed,gain_settled,epoch_ack,prefilled)):
            self.state='ready';self.ready=True
        elif self.state in ('settling','ready') and not source_qualified:
            self.state='fault';self.ready=False
        return self.ready

    def launch(self,time,epoch):
        if not self.ready or self.state!='ready' or epoch!=self.epoch or not self.time<=time<=self.deadline:
            raise ValueError('unready/stale/late launch')
        self.output=True;self.state='active'
        if getattr(self,'next_configuration',None) is not None:
            self.configuration=self.next_configuration;self.next_configuration=None


def gain_feedback_bound(*,observation_samples=16,sample_hz=37.5e6,
                        d2h_words_hz=156.25e6,h2d_words_hz=312.5e6,
                        fpga_s=100e-9,settling_s=400e-9):
    vals=(observation_samples,sample_hz,d2h_words_hz,h2d_words_hz,fpga_s,settling_s)
    if not all(math.isfinite(x) and x>=0 for x in vals) or min(sample_hz,d2h_words_hz,h2d_words_hz)<=0:
        raise ValueError('gain loop inputs')
    # Each frame path reserves wait, snapshot/staging and emission; no zero-latency mailbox.
    parts=dict(frontend=150e-9,observe=observation_samples/sample_hz,return_transport=3*64/d2h_words_hz,
               decision=fpga_s,command_transport=3*64/h2d_words_hz,
               cdc_and_commit=6/(h2d_words_hz/2),settle=settling_s,
               first_clean_sample=1/sample_hz)
    return dict(parts_s=parts,total_s=sum(parts.values()))


def cdr_holdover_error(*,line_hz,run_ui,residual_ppm=50,frequency_slew_ppm_s=330e6,
                       initial_ui=.0625,other_ui=.0625):
    vals=(line_hz,run_ui,residual_ppm,frequency_slew_ppm_s,initial_ui,other_ui)
    if not all(math.isfinite(x) and x>=0 for x in vals) or line_hz==0:raise ValueError('CDR budget')
    duration=run_ui/line_hz
    error=initial_ui+other_ui+run_ui*residual_ppm/1e6+0.5*line_hz*frequency_slew_ppm_s/1e6*duration**2
    return dict(error_ui=error,admissible=error<.25)


def ssc_tracking_screen(*,line_hz=2.5e9,loop_hz=2.5e6,modulation_hz=33e3,
                        spread_ppm=5000,static_ppm=0,damping=.707):
    """Linear type-II phase/frequency loop, already frequency-acquired.

    Euler integration with loop-scaled timestep; no transistor noise, detector
    nonlinearity, quantization or cold frequency-acquisition claim. Discard first
    modulation period, observe next two periods, reject phase error > allocation.
    """
    vals=(line_hz,loop_hz,modulation_hz,spread_ppm,static_ppm,damping)
    if not all(math.isfinite(x) for x in vals) or min(line_hz,loop_hz,modulation_hz,damping)<=0 or spread_ppm<0:
        raise ValueError('loop parameters')
    if not -6000<=static_ppm-spread_ppm<=static_ppm<=1000:
        raise ValueError('incoming offset outside selected envelope')
    omega=2*math.pi*loop_hz
    steps=math.ceil(1/modulation_hz/min(2e-9,1/(100*loop_hz)))
    dt=1/modulation_hz/steps
    phase=estimate=0.;frequency=line_hz*static_ppm/1e6
    maximum=0.;frequency_residual=0.
    for i in range(3*steps):
        frac=(i%steps)/steps
        triangle=1-abs(2*frac-1)
        incoming=line_hz*(static_ppm-spread_ppm*triangle)/1e6
        error=phase-estimate
        corrected=frequency+2*damping*omega*error
        if i>=steps:
            maximum=max(maximum,abs(error))
            frequency_residual=max(frequency_residual,abs(incoming-corrected)/line_hz*1e6)
        frequency+=omega**2*error*dt
        estimate+=corrected*dt;phase+=incoming*dt
    return dict(phase_error_ui=maximum,residual_ppm=frequency_residual,
                admissible=maximum<=.0625 and frequency_residual<=50,
                scope='linear acquired-loop screen, not physical CDR proof')


def acquisition_admission(training_s,*,reserve_s,rounds=1,stale_pairs=24,**gain_args):
    if not all(math.isfinite(x) and x>=0 for x in (training_s,reserve_s)) or type(rounds) is not int or rounds<0:
        raise ValueError('acquisition budget')
    if type(stale_pairs) is not int or not 0<=stale_pairs<=24:
        raise ValueError('Fast gain path reserves at most 24 stale sample pairs')
    duration=rounds*gain_feedback_bound(**gain_args)['total_s']
    invalid_pairs=(stale_pairs+math.ceil(gain_args.get('settling_s',400e-9)*
                   gain_args.get('sample_hz',37.5e6))) if rounds else 0
    from rf_gain_command import MAX_INVALID_PAIRS
    status_fits=invalid_pairs<=MAX_INVALID_PAIRS
    return dict(gain_time_s=duration,remaining_s=training_s-reserve_s-duration,
                invalid_pairs_per_update=invalid_pairs,status_count_fits=status_fits,
                admissible=duration+reserve_s<=training_s and status_fits)


def hop_admission(previous_end_s,next_window_s,*,uncertainty_s=5e-6,hop_s=50e-6):
    vals=(previous_end_s,next_window_s,uncertainty_s,hop_s)
    if not all(math.isfinite(x) and x>=0 for x in vals):raise ValueError('schedule')
    margin=next_window_s-previous_end_s-uncertainty_s-hop_s
    return dict(margin_s=margin,admissible=margin>=0)


def periodic_clock_elapsed(cycles, *, period_ui, phase_cycles, offset_ppm, depth_ppm):
    """Elapsed reference UIs for triangular frequency modulation versus cycle count.

    Unselected acquisition hypothesis matching the cycle-indexed SSC fixture.
    This is not a claim that every physical SSC source has this exact waveform.
    """
    import numpy as np
    cycles=np.asarray(cycles,dtype=float)
    if (not np.all(np.isfinite(cycles)) or not all(math.isfinite(v) for v in
            (period_ui,phase_cycles,offset_ppm,depth_ppm)) or period_ui<=0 or
            depth_ppm<0 or 1+(offset_ppm-depth_ppm)*1e-6<=0):
        raise ValueError('Finite positive-period clock law required')
    a=1+offset_ppm*1e-6;d=depth_ppm*1e-6
    if d<1e-10:return cycles/a
    def primitive(x):
        integer=np.floor(x);r=x-integer
        half=-np.log1p(-d/a)/(2*d)
        first=-np.log1p(-2*d*np.minimum(r,.5)/a)/(2*d)
        second=half+np.log1p(2*d*np.maximum(r-.5,0)/(a-d))/(2*d)
        return integer*(2*half)+np.where(r<=.5,first,second)
    return period_ui*(primitive(cycles/period_ui+phase_cycles)-primitive(phase_cycles))


def fit_periodic_clock(observations, *, line_hz, modulation_hz_bounds=(30000.,33000.),
                       training_count=96, phase_limit_ui=.0625):
    """Fit past local (inferred cycle count, measured edge UI) observations only.

    A finite 128-observation acquisition experiment: first96 fit, last32 validate
    without refitting. Costs, coefficient quantization and execution latency are
    unallocated. No receiver readiness follows from this fit alone.
    """
    import numpy as np
    from scipy.optimize import least_squares
    data=np.asarray(observations,dtype=float)
    low,high=modulation_hz_bounds
    if (data.shape!=(128,2) or not np.all(np.isfinite(data)) or
            not np.all(np.diff(data,axis=0)>0) or training_count!=96 or
            not all(math.isfinite(v) for v in (line_hz,low,high,phase_limit_ui)) or
            not 0<low<high or line_hz<=0 or phase_limit_ui<=0):
        raise ValueError('128 ordered observations and finite acquisition bounds required')
    origin=data[0].copy();x=data[:,0]-origin[0];y=data[:,1]-origin[1]
    if x[training_count-1]<2*line_hz/low:
        raise ValueError('Training must span at least two longest modulation cycles')
    def elapsed(p,at):
        khz,phase,offset,depth,intercept=p
        return intercept+periodic_clock_elapsed(at,period_ui=line_hz/(khz*1000),
            phase_cycles=phase,offset_ppm=offset,depth_ppm=depth)
    def residual(p):return elapsed(p,x[:training_count])-y[:training_count]
    best=None
    for phase in (0.,.25,.5,.75):
        fit=least_squares(residual,[(low+high)/2000,phase,0.,4000.,0.],
            bounds=([low/1000,-1.,-6000.,0.,-.25],
                    [high/1000,2.,1000.,6000.,.25]),
            x_scale=[1.,1.,1000.,5000.,.01],max_nfev=200,
            ftol=1e-10,xtol=1e-10,gtol=1e-10)
        score=float(np.dot(fit.fun,fit.fun))
        if best is None or score<best[0]:best=(score,fit)
    fit=best[1];khz,phase,offset,depth,intercept=map(float,fit.x)
    errors=elapsed(fit.x,x)-y
    train_peak=float(max(abs(errors[:training_count])))
    validation_peak=float(max(abs(errors[training_count:])))
    return dict(period_ui=line_hz/(khz*1000),phase_cycles=phase%1.,
        offset_ppm=offset,depth_ppm=depth,intercept_ui=intercept,
        origin_cycle=float(origin[0]),origin_edge_ui=float(origin[1]),
        last_observed_cycle=float(data[-1,0]),last_observed_edge_ui=float(data[-1,1]),
        training_count=training_count,validation_count=len(data)-training_count,
        training_peak_error_ui=train_peak,validation_peak_error_ui=validation_peak,
        phase_limit_ui=phase_limit_ui,optimizer_converged=bool(fit.success),
        observed_phase_validation_pass=bool(fit.success and max(train_peak,validation_peak)<=phase_limit_ui),
        qualified=False,
        scope='Optional cycle-indexed triangular-source hypothesis learned from local observations. Held-out phase agreement is not a future error bound, oscillator control, acquisition deadline or physical implementation proof.')


def periodic_clock_period_prediction(fit,cycles):
    """Predict period from a frozen acquired hypothesis, not source timing."""
    import numpy as np
    x=np.asarray(cycles,dtype=float)-fit['origin_cycle']
    phase=(x/fit['period_ui']+fit['phase_cycles'])%1
    triangular=1-np.abs(2*phase-1)
    return 1/(1+(fit['offset_ppm']-fit['depth_ppm']*triangular)*1e-6)



def encode_clock_observation(cycle,edge_ui,epoch):
    """Experimental ten-byte record: epoch16, local count24, reference UI24.16."""
    if (type(cycle) is not int or not 0<=cycle<1<<24 or type(epoch) is not int or
            not 0<=epoch<1<<16 or not math.isfinite(edge_ui) or edge_ui<0):
        raise ValueError('Clock observation outside record range')
    ticks=round(edge_ui*(1<<16))
    if not 0<=ticks<1<<40:raise ValueError('Clock observation timestamp overflow')
    return ((epoch<<64)|(cycle<<40)|ticks).to_bytes(10,'big')


def decode_clock_observation(record,epoch):
    if not isinstance(record,bytes) or len(record)!=10:raise ValueError('Ten-byte clock observation required')
    word=int.from_bytes(record,'big')
    if word>>64!=epoch:raise ValueError('Stale clock observation epoch')
    return (word>>40)&((1<<24)-1),(word&((1<<40)-1))/(1<<16)


# Fixed 64-byte experimental command, including version/epoch/reserved header.
_CLOCK_COEFFICIENT_FIELDS=(('period_ui',24),('phase_cycles',40),
    ('offset_ppm',24),('depth_ppm',24),('intercept_ui',40),
    ('origin_cycle',0),('origin_edge_ui',24))


def encode_clock_coefficients(fit,epoch):
    if type(epoch) is not int or not 0<=epoch<65536:
        raise ValueError('Invalid coefficient epoch')
    record=bytes([1])+epoch.to_bytes(2,'big')+bytes(5)
    for key,fraction in _CLOCK_COEFFICIENT_FIELDS:
        value=fit[key]
        if not math.isfinite(value):raise ValueError('Nonfinite clock coefficient')
        integer=round(value*(1<<fraction))
        if not -(1<<63)<=integer<1<<63:raise ValueError('Clock coefficient overflow')
        record+=integer.to_bytes(8,'big',signed=True)
    decode_clock_coefficients(record,epoch)
    return record


def decode_clock_coefficients(record,epoch):
    if not isinstance(record,bytes) or len(record)!=64:
        raise ValueError('64-byte coefficient command required')
    if record[0]!=1 or any(record[3:8]):raise ValueError('Invalid coefficient header')
    if int.from_bytes(record[1:3],'big')!=epoch:raise ValueError('Stale coefficient epoch')
    result={key:int.from_bytes(record[8+8*i:16+8*i],'big',signed=True)/(1<<fraction)
        for i,(key,fraction) in enumerate(_CLOCK_COEFFICIENT_FIELDS)}
    if not (0<result['period_ui']<1<<24 and 0<=result['phase_cycles']<1 and
            -6000<=result['offset_ppm']<=1000 and 0<=result['depth_ppm']<=6000 and
            abs(result['intercept_ui'])<=.25 and 0<=result['origin_cycle']<1<<24 and
            0<=result['origin_edge_ui']<1<<24):
        raise ValueError('Clock coefficient outside controller range')
    result['phase_limit_ui']=.0625  # Local safety limit, never widened by host.
    return result


class PeriodicObservationLink:
    """Finite chip FIFO to FPGA-owned history; explicit byte serialization/CDC.

    Fixed observation records are an experimental payload, not an implemented
    management opcode. Acquisition owns the reserved D2H service in this model.
    """
    def __init__(self,line_hz,*,word_hz,latency_s,queue_bits,coefficient_return_s,epoch=0,word_bits=8):
        if (not all(math.isfinite(v) for v in (line_hz,word_hz,latency_s,coefficient_return_s)) or
                line_hz<=0 or word_bits not in (8,10) or not 0<word_hz<=(100e6 if word_bits==8 else 312.5e6) or min(latency_s,coefficient_return_s)<0 or
                type(queue_bits) is not int or queue_bits<80 or type(epoch) is not int or not 0<=epoch<1<<16):
            raise ValueError('Finite observation service required')
        self.line_hz=line_hz;self.word_hz=word_hz;self.word_bits=word_bits;self.latency_ui=latency_s*line_hz
        self.return_ui=coefficient_return_s*line_hz;self.queue_bits=queue_bits;self.epoch=epoch
        self.pending=();self.fpga_observations=();self.last_finish_ui=-math.inf
        self.last_delivery_ui=None;self.sent_records=0;self.peak_queue_bits=0;self.fault=None

    def advance(self,now_ui):
        while self.pending and self.pending[0][0]<=now_ui and self.fault is None:
            finish,record=self.pending[0];self.pending=self.pending[1:]
            try:observation=decode_clock_observation(record,self.epoch)
            except ValueError:
                self.fault='observation_epoch';return
            if self.fpga_observations and any(a<=b for a,b in zip(observation,self.fpga_observations[-1])):
                self.fault='observation_order';return
            self.fpga_observations+=(observation,);self.last_delivery_ui=finish

    def enqueue(self,cycle,edge_ui,now_ui):
        self.advance(now_ui)
        if self.fault is not None or self.sent_records>=128:return
        if 80*(len(self.pending)+1)>self.queue_bits:
            self.fault='observation_overflow';return
        try:record=encode_clock_observation(cycle,edge_ui,self.epoch)
        except ValueError:
            self.fault='observation_range';return
        start=max(now_ui+self.latency_ui,self.last_finish_ui)
        finish=start+math.ceil(80/self.word_bits)*self.line_hz/self.word_hz
        self.pending+=((finish,record),);self.last_finish_ui=finish;self.sent_records+=1
        self.peak_queue_bits=max(self.peak_queue_bits,80*len(self.pending))


class PeriodicClockController:
    """Optional finite-history learner with delayed, revocable feedforward.

    State containers are immutable so a receiver can copy this controller for
    forecast/commit. The assigned compute delay is a requirement, not benchmarked
    hardware. A rejected hypothesis latches invalid until explicit reacquisition.
    """
    def __init__(self,line_hz,compute_delay_s,observation_link=None):
        if not all(math.isfinite(v) and v>0 for v in (line_hz,compute_delay_s)):
            raise ValueError('Positive finite line rate and processing delay required')
        self.line_hz=line_hz;self.compute_delay_ui=line_hz*compute_delay_s
        self.link=None if observation_link is None else PeriodicObservationLink(line_hz,**observation_link)
        self.local_validated=False
        self.local_fit=None;self.pending_coefficients=None
        self.observations=();self.next_observation=2048;self.fit=None
        self.state='collecting';self.ready_after_ui=math.inf
        self.activation_cycle=None;self.invalid_cycle=None;self.invalid_reason=None
        self.last_period=None;self.maximum_observed_error_ui=0.

    def clone(self):
        import copy
        result=copy.copy(self)
        if self.link is not None:result.link=copy.copy(self.link)
        return result

    def _fit_received(self,available_ui):
        if len(self.observations)!=128 or self.fit is not None:return
        self.fit=fit_periodic_clock(self.observations,line_hz=self.line_hz)
        if self.fit['observed_phase_validation_pass']:
            self.state='processing'
            if self.link is not None:
                self.pending_coefficients=encode_clock_coefficients(self.fit,self.link.epoch)
            self.ready_after_ui=available_ui+self.compute_delay_ui+(0. if self.link is None else self.link.return_ui)
        else:
            self.state='invalid';self.invalid_cycle=self.observations[-1][0];self.invalid_reason='heldout_fit_rejected'

    def observe(self,cycle,edge_ui,now_ui=None):
        if self.state=='invalid':return
        if self.fit is not None:
            # FPGA-side fit is not locally available before its command arrives.
            if self.link is not None and self.state!='active':return
            f=self.fit if self.link is None else self.local_fit
            expected=f['origin_edge_ui']+f['intercept_ui']+float(periodic_clock_elapsed(
                cycle-f['origin_cycle'],**{k:f[k] for k in
                    ('period_ui','phase_cycles','offset_ppm','depth_ppm')}))
            error=abs(edge_ui-expected)
            self.maximum_observed_error_ui=max(self.maximum_observed_error_ui,error)
            if error>f['phase_limit_ui']:
                self.state='invalid';self.invalid_cycle=cycle;self.invalid_reason='observed_phase_mismatch'
                self.local_validated=False
            elif self.state=='active':self.local_validated=True
            return
        if cycle<self.next_observation:return
        self.next_observation=cycle+2048
        if self.link is not None:
            self.link.enqueue(cycle,edge_ui,edge_ui if now_ui is None else now_ui)
        else:
            self.observations+=((cycle,edge_ui),)
            self._fit_received(edge_ui)

    def period_slew_bound(self):
        """Maximum absolute commanded period change per local cycle."""
        if self.state!='active':return 0.
        f=self.fit if self.link is None else self.local_fit
        minimum_frequency=1+(f['offset_ppm']-f['depth_ppm'])*1e-6
        return 2*f['depth_ppm']*1e-6/(f['period_ui']*minimum_frequency**2)

    def step(self,cycle,previous_sample_ui):
        """Return (newly active, predicted period, feedforward period increment)."""
        newly_active=False
        if self.link is not None and self.state!='invalid':
            self.link.advance(previous_sample_ui)
            self.observations=self.link.fpga_observations  # FPGA-owned, not chip RAM.
            if self.link.fault is not None:
                self.state='invalid';self.invalid_cycle=cycle;self.invalid_reason=self.link.fault
            elif self.state=='collecting':self._fit_received(self.link.last_delivery_ui)
        if self.state=='processing' and previous_sample_ui>=self.ready_after_ui:
            if self.link is not None:
                try:self.local_fit=decode_clock_coefficients(self.pending_coefficients,self.link.epoch)
                except ValueError:
                    self.state='invalid';self.invalid_cycle=cycle;self.invalid_reason='coefficient_command'
                    return False,None,0.
            self.state='active';self.activation_cycle=cycle;newly_active=True;self.local_validated=False
        if self.state!='active':return False,None,0.
        f=self.fit if self.link is None else self.local_fit
        phase=((cycle-f['origin_cycle'])/f['period_ui']+f['phase_cycles'])%1.
        period=1/(1+(f['offset_ppm']-f['depth_ppm']*(1-abs(2*phase-1)))*1e-6)
        increment=0. if self.last_period is None else period-self.last_period
        self.last_period=period
        return newly_active,period,increment
