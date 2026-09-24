"""Finite two-node USB/shared-pad circuit and protocol-independent timed fixtures.

Lumped parameters are hypotheses. No transmission-line/package or USB PHY
compliance claim. Local and external source power are accounted separately.
"""
import math
import numpy as np
from scipy.linalg import expm


class SharedWiredPad:
    def __init__(self,cap_f=2e-12,mutual_f=.2e-12,off_cap_f=.3e-12):
        if not all(math.isfinite(x) and x>0 for x in (cap_f,mutual_f,off_cap_f)):
            raise ValueError('Positive pad capacitances')
        self.C=np.array([[cap_f+off_cap_f+mutual_f,-mutual_f],[-mutual_f,cap_f+off_cap_f+mutual_f]])
        self.invC=np.linalg.inv(self.C);self.voltage=np.zeros(2);self.time=0.
        self.mode='isolated';self.role='device';self.speed='fs'
        self.local='Z';self.peer='Z';self.attached=False
        self.peer_supply=3.3;self.hs_current=.4/(1/(1/45+1/45))
        self.source_energy_j=0.;self.external_energy_j=0.;self.dissipated_j=0.

    def configure(self,mode,role='device',speed='fs',attached=False):
        if mode not in ('isolated','serial','usb') or role not in ('host','device') or speed not in ('ls','fs','hs'):
            raise ValueError('Pad profile')
        if self.local!='Z' or self.peer!='Z':raise ValueError('Release both drivers before pad reconfiguration')
        self.mode=mode;self.role=role;self.speed=speed;self.attached=bool(attached)

    def drive(self,local='Z',peer='Z'):
        if local not in ('Z','J','K','SE0') or peer not in ('Z','J','K','SE0'):
            raise ValueError('Line state')
        if self.mode!='usb' and (local!='Z' or peer!='Z'):raise ValueError('USB branch is isolated')
        if local!='Z' and peer!='Z':raise ValueError('USB bus contention')
        if self.speed=='hs' and (local=='SE0' or peer=='SE0'):
            raise ValueError('HS zero state is driver release, not FS push-pull SE0')
        self.local=local;self.peer=peer

    def electrical(self,voltage,rail):
        """Return dV/dt, local supply current, external power, dissipated power."""
        v=np.asarray(voltage);current=np.zeros(2);supply=0.;external=0.;loss=0.
        def resistor(node,target,r,owner):
            nonlocal supply,external,loss
            i=(target-v[node])/r;current[node]+=i;loss+=i*i*r
            if owner=='local':supply+=i
            elif owner=='peer':external+=target*i
        for n in range(2):resistor(n,0.,1e9,'ground')
        if self.mode=='serial':
            # Isolated USB branch contributes C_off; serial CM comes from peer fixture.
            for n in range(2):resistor(n,.8,50.,'peer')
        if self.mode=='usb':
            if self.speed=='hs':
                for n in range(2):
                    resistor(n,0.,45.,'ground')
                    if self.attached:resistor(n,0.,45.,'ground')
            else:
                # Host pull-downs; a connected device advertises FS on D+ or LS on D-.
                for n in range(2):
                    if self.role=='host' or self.attached:resistor(n,0.,15000.,'ground')
                if self.role=='device' or self.attached:
                    local_device=self.role=='device'
                    resistor(1 if self.speed=='ls' else 0,rail if local_device else self.peer_supply,1500.,'local' if local_device else 'peer')
            for state,owner,source in ((self.local,'local',rail),(self.peer,'peer',self.peer_supply)):
                if state=='Z':continue
                jnode=1 if self.speed=='ls' else 0
                high=jnode if state=='J' else 1-jnode
                if self.speed=='hs':
                    # Current source loses compliance above its supply, rather than infinite drive.
                    i=self.hs_current*max(0.,min(1.,(source-v[high])/.3))
                    current[high]+=i;loss+=(source-v[high])*i
                    if owner=='local':supply+=i
                    else:external+=source*i
                else:
                    for n in range(2):resistor(n,source if n==high and state!='SE0' else 0.,30.,owner if n==high and state!='SE0' else 'ground')
        return self.invC@current,supply,external,loss

    def energy(self):return .5*float(self.voltage@self.C@self.voltage)

    def observe(self):
        p,n=self.voltage
        return dict(dp_v=float(p),dm_v=float(n),differential_v=float(p-n),
                    squelch=abs(p-n)<.1,se0=max(p,n)<.3,
                    j=bool((n>p) if self.speed=='ls' else (p>n)))

    def advance(self,time,rail=3.3):
        """Standalone exact affine step, used to check the coupled ODE primitive."""
        if not math.isfinite(time) or time<self.time or not rail>0:raise ValueError('Pad time/rail')
        dt=time-self.time
        if dt==0:return
        # Remains in the HS current-source compliance region for valid USB levels.
        b=self.electrical(np.zeros(2),rail)[0]
        a=np.column_stack([self.electrical(np.eye(2)[i]*.01,rail)[0]-b for i in range(2)])/.01
        aug=np.zeros((3,3));aug[:2,:2]=a;aug[:2,2]=b
        out=(expm(aug*dt)@np.r_[self.voltage,1])[:2]
        if self.speed=='hs' and self.mode=='usb' and max(out)>rail-.3:
            raise ValueError('Use coupled nonlinear solver outside HS compliance')
        self.voltage=out;self.time=time


def usb_nrzi(bits):
    level=1;ones=0;out=[]
    for bit in bits:
        if bit not in (0,1):raise ValueError('Binary USB data')
        if bit==0:level^=1
        out.append(level);ones=ones+1 if bit else 0
        if ones==6:level^=1;out.append(level);ones=0
    return out


def usb_decode(levels):
    previous=1;ones=0;out=[]
    for level in levels:
        if level not in (0,1):raise ValueError('Binary line levels')
        bit=int(level==previous);previous=level
        if ones==6:
            if bit:raise ValueError('USB bit stuffing violation')
            ones=0;continue
        out.append(bit);ones=ones+1 if bit else 0
    if ones==6:raise ValueError('Missing stuffed bit')
    return out


def sata_oob(kind):
    if kind not in ('reset','init','wake'):raise ValueError('SATA OOB kind')
    burst=160/1.5e9;gap=(160 if kind=='wake' else 480)/1.5e9
    return [(i*(burst+gap),i*(burst+gap)+burst) for i in range(6)]


def detect_oob(intervals,tolerance=.15):
    """Envelope-only detector: reset/init electrically identical; no CDR oracle."""
    if not 0<tolerance<.5:raise ValueError('OOB tolerance')
    if len(intervals)<4:return None
    widths=[b-a for a,b in intervals]
    gaps=[intervals[i+1][0]-intervals[i][1] for i in range(len(intervals)-1)]
    near=lambda vals,nominal:all(abs(v/nominal-1)<=tolerance for v in vals)
    if not near(widths,160/1.5e9):return None
    if near(gaps,160/1.5e9):return 'wake'
    if near(gaps,480/1.5e9):return 'reset_or_init'
    return None


def response_budget(*,word_hz,rx_words,tx_words,fpga_s,turnaround_s,deadline_s,
                    phase_words=1,queue_words=0,framed=False):
    vals=(word_hz,rx_words,tx_words,fpga_s,turnaround_s,deadline_s,phase_words,queue_words)
    if not all(math.isfinite(v) for v in vals) or word_hz<=0 or deadline_s<=0 or any(v<0 for v in vals[1:]):
        raise ValueError('Response envelope')
    # Each direction can just miss its service point; old framed path also waits a frame.
    transport=(rx_words+tx_words+2*phase_words+queue_words+(128 if framed else 0))/word_hz
    elapsed=transport+fpga_s+turnaround_s
    return dict(elapsed_s=elapsed,margin_s=deadline_s-elapsed,met=elapsed<=deadline_s)


def usb_framed_turnaround(frame_words=8,word_hz=250e6,fpga_s=40e-9,
                          analog_s=34e-9,cdc_words=4,queue_words=4,packing_bits=20):
    """Conservative round-trip bound for the existing two-bank frame snapshots.

    Each direction: <1 frame to snapshot, one frame until emission, <=1 frame
    to deliver the last word. USB-IF EL_22 requires 8..192 HS bit times for
    ordinary host/device responses, measured at the relevant port boundaries.
    No built-in-hub or cable allowance is consumed by this local chip/FPGA budget.
    """
    values=(word_hz,fpga_s,analog_s,cdc_words,queue_words,packing_bits)
    if frame_words not in (8,64) or not all(math.isfinite(v) for v in values) or word_hz<=0 or any(v<0 for v in values[1:]):
        raise ValueError('USB framed timing envelope')
    worst=(6*frame_words+cdc_words+queue_words)/word_hz+fpga_s+analog_s+packing_bits/480e6
    earliest=fpga_s+analog_s
    minimum=8/480e6;maximum=192/480e6
    return dict(frame_words=frame_words,word_hz=word_hz,
                raw_payload_capacity_bps=(frame_words-5)*10*word_hz/frame_words,
                earliest_s=earliest,worst_s=worst,minimum_s=minimum,maximum_s=maximum,
                minimum_guard_s=max(0.,minimum-earliest),margin_s=maximum-max(worst,minimum),
                meets_bound=max(worst,minimum)<=maximum,
                assumptions=dict(fpga_s=fpga_s,analog_s=analog_s,cdc_words=cdc_words,
                                 queue_words=queue_words,packing_bits=packing_bits))


class BurstEnvelopeReceiver:
    """Generic first-order envelope, hysteretic comparator and timed burst counter.

    Input is a rectified envelope voltage, not decoded burst timestamps. Detector
    windows are supplied by the profile. This reduction has ideal comparator
    thresholds and a frozen supply; RF rectification, package and clock error
    need qualification. Emits completed patterns only after observed inactivity.
    """
    def __init__(self,patterns,*,tau_s=10e-9,on_v=.12,off_v=.08,min_bursts=4):
        if (not all(math.isfinite(v) and v>0 for v in (tau_s,on_v,off_v)) or
                off_v>=on_v or not isinstance(min_bursts,int) or min_bursts<2):
            raise ValueError('Envelope detector parameters')
        self.patterns=dict(patterns)
        for widths,gaps,release in self.patterns.values():
            if (not all(math.isfinite(v) and v>0 for v in (*widths,*gaps,release)) or
                    not widths[0]<widths[1] or not gaps[0]<gaps[1] or release<=gaps[1]):
                raise ValueError('Burst timing windows')
        if not self.patterns:raise ValueError('At least one pattern required')
        self.tau=tau_s;self.on=on_v;self.off=off_v;self.minimum=min_bursts
        self.time=0.;self.voltage=0.;self.target=0.;self.active=False
        self.rise=None;self.fall=None;self.candidates=set();self.count=0;self.events=[]

    def _edge(self,active,time):
        if active:
            if self.fall is not None:
                gap=time-self.fall
                self.candidates={k for k in self.candidates
                    if self.patterns[k][1][0]<=gap<=self.patterns[k][1][1]}
            if not self.candidates:
                self.candidates=set(self.patterns);self.count=0
            self.rise=time
        else:
            width=time-self.rise
            self.candidates={k for k in self.candidates
                if self.patterns[k][0][0]<=width<=self.patterns[k][0][1]}
            self.count=self.count+1 if self.candidates else 0
            self.fall=time
        self.active=active

    def advance(self,time):
        if not math.isfinite(time) or time<self.time:raise ValueError('Monotonic finite detector time')
        threshold=self.off if self.active else self.on
        crossing=None
        if ((self.active and self.target<threshold<self.voltage) or
                (not self.active and self.voltage<threshold<self.target)):
            crossing=self.time-self.tau*math.log((threshold-self.target)/(self.voltage-self.target))
        self._release(min(time,crossing) if crossing is not None else time)
        if crossing is not None and crossing<=time:self._edge(not self.active,crossing)
        self.voltage=self.target+(self.voltage-self.target)*math.exp(-(time-self.time)/self.tau)
        self.time=time
        self._release(time)
        return list(self.events)

    def _release(self,time):
        if not self.active and self.fall is not None and self.count>=self.minimum:
            completed=[k for k in self.candidates if time>=self.fall+self.patterns[k][2]]
            if len(completed)==1:
                key=completed[0]
                self.events.append(dict(kind=key,time_s=self.fall+self.patterns[key][2],bursts=self.count))
                self.candidates=set();self.count=0;self.fall=None

    def drive(self,voltage,time):
        if not math.isfinite(voltage) or voltage<0:raise ValueError('Nonnegative finite envelope')
        self.advance(time);self.target=voltage

    @property
    def next_event(self):
        threshold=self.off if self.active else self.on
        crossing=math.inf
        if ((self.active and self.target<threshold<self.voltage) or
                (not self.active and self.voltage<threshold<self.target)):
            crossing=self.time-self.tau*math.log((threshold-self.target)/(self.voltage-self.target))
        release=math.inf
        if not self.active and self.fall is not None and self.count>=self.minimum:
            release=min((self.fall+self.patterns[k][2] for k in self.candidates),default=math.inf)
        return min(crossing,release)


def sata_envelope_receiver(**kwargs):
    """Candidate interior windows, not complete SATA detector acceptance limits.

    Quiet-release delays follow SATA 1.0 section 6.7.4. Burst/gap +/-15%
    windows retain the earlier fixture's candidate hypothesis for comparison.
    """
    burst=160/1.5e9
    return BurstEnvelopeReceiver({
        'reset_or_init':((.85*burst,1.15*burst),(.85*480/1.5e9,1.15*480/1.5e9),525e-9),
        'wake':((.85*burst,1.15*burst),(.85*burst,1.15*burst),175e-9)},**kwargs)


class SataOobStartup:
    """External-FPGA startup reduction driven by received envelope observations.

    Enters await_alignment, then times out without alignment; never asserts PHY
    ready. Local reaction and overall
    timeout are exploration parameters, not standard timing claims. Actual ALIGN,
    calibration, D10.2, retry and power-management behavior remain unimplemented.
    """
    def __init__(self,role,*,reaction_s=100e-9,timeout_s=100e-6,detector_tau_s=10e-9):
        if role not in ('host','device') or not 0<reaction_s<timeout_s or not math.isfinite(timeout_s):
            raise ValueError('Startup role/timing')
        self.role=role;self.reaction=reaction_s;self.timeout=timeout_s
        self.detector=sata_envelope_receiver(tau_s=detector_tau_s)
        self.state='stopped';self.time=0.;self.deadline=math.inf
        self.observed=0;self.history=[];self.transmissions=[]
        self.oob_completed_at=None;self.fault_reason=None

    def _transmit(self,kind,start):
        self.transmissions.append(dict(kind=kind,start_s=start,
            intervals=[(start+a,start+b) for a,b in sata_oob(kind)]))

    def start(self,time=0.):
        if self.state!='stopped' or not math.isfinite(time) or time<self.time:
            raise ValueError('Stopped startup controller required')
        self.detector.advance(time);self.time=time;self.deadline=time+self.timeout
        self.state='wait_init' if self.role=='host' else 'wait_reset'
        if self.role=='host':self._transmit('reset',time)

    def advance(self,time):
        if not math.isfinite(time) or time<self.time:raise ValueError('Monotonic startup time')
        if time>self.next_event:raise ValueError('Do not skip startup observation/deadline')
        self.detector.advance(time)
        for event in self.detector.events[self.observed:]:
            when=event['time_s'];kind=event['kind']
            if when>=self.deadline:
                self.state='fault';self.fault_reason='startup timeout'
            before=self.state
            if self.state=='wait_reset' and kind=='reset_or_init':
                self._transmit('init',when+self.reaction);self.state='wait_wake'
            elif self.state=='wait_init' and kind=='reset_or_init':
                self._transmit('wake',when+self.reaction);self.state='wait_wake'
            elif self.state=='wait_wake' and kind=='wake':
                if self.role=='device':self._transmit('wake',when+self.reaction)
                self.state='await_alignment';self.oob_completed_at=when
            elif self.state not in ('fault','stopped'):
                self.state='fault';self.fault_reason='unexpected OOB during startup'
            self.history.append(dict(time_s=when,kind=kind,before=before,after=self.state))
        self.observed=len(self.detector.events)
        if time>=self.deadline and self.state not in ('stopped','fault'):
            self.state='fault';self.fault_reason='startup timeout'
        self.time=time

    def drive_received(self,voltage,time):
        self.advance(time);self.detector.drive(voltage,time)

    @property
    def phy_ready(self):return False

    @property
    def next_event(self):
        timeout=self.deadline if self.state not in ('stopped','fault') else math.inf
        return min(self.detector.next_event,timeout)
