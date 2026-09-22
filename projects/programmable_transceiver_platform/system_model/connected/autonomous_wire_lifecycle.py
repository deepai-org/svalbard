"""Independent bounded wired PLL owns full-chip word and bit scheduling."""
import copy
import math
from autonomous_pll import AutonomousPLL
from pll_serializer import PLLSerializer
from timed_management import ManagedChip


class AutonomousWireChip(ManagedChip):
    WIRE_PLL_CLASS=AutonomousPLL
    def __init__(self,wire_free_offset=-.04,wire_bandwidth_hz=1e6,wire_reference_ppm=0.,wire_reference_divider=1,**kwargs):
        if not math.isfinite(wire_free_offset) or not math.isfinite(wire_bandwidth_hz) or wire_bandwidth_hz<=0:
            raise ValueError('Invalid wired oscillator assumptions')
        if not math.isfinite(wire_reference_ppm) or abs(wire_reference_ppm)>1000:
            raise ValueError('Reference offset exceeds declared +/-1000ppm model envelope')
        if 1.25e9*(1+wire_free_offset)<=200e6:
            raise ValueError('VCO frequency must remain positive in both modes')
        if wire_reference_divider not in (1,4):raise ValueError('Unsupported wired reference divider')
        self.wire_reference_divider=wire_reference_divider
        self.wire_reference_ppm=wire_reference_ppm
        self.wire_pll=None;self.next_wire_reference=math.inf
        self.wire_free_offset=wire_free_offset;self.wire_bandwidth=wire_bandwidth_hz
        self.wire_lock_history=[];self.wire_phase_target=None
        super().__init__(**kwargs)

    def make_serializer(self,time):
        rate=self.channel.rate;previous=self.wire_pll
        factor=self.wire_reference_divider;pfd_reference=40e6/factor
        if previous is None or previous.divider!=rate/pfd_reference:
            new=self.WIRE_PLL_CLASS(reference_hz=pfd_reference*(1+self.wire_reference_ppm*1e-6),
                              divider=rate/pfd_reference,free_hz=rate*(1+self.wire_free_offset),
                              bandwidth_hz=self.wire_bandwidth,phase_cycles=.2/factor,
                              lock_phase_cycles=.01/factor,lock_frequency_hz=4000./factor)
            new.time=time
            if previous is not None:
                # Retuning uses a declared VCO band change and divider reset.
                # Preserve filter charge; the new divider begins with phase error.
                new.integral=previous.integral
                new.phase_offset=previous.output_phase_cycles-new.output_phase_cycles
            self.wire_pll=new
        self.wire_pll.good=0;self.wire_pll.locked=False
        self.wire_ref_origin=time
        if factor>1:
            # Reset the reference prescaler; count four future input edges,
            # including when configuration occurs between40MHz edges.
            input_hz=40e6*(1+self.wire_reference_ppm*1e-6)
            index=time*input_hz
            if abs(index-round(index))<1e-10:index=round(index)
            self.wire_ref_origin=math.floor(index)/input_hz
        self.wire_ref_index=1
        self.next_wire_reference=self.wire_ref_origin+1/self.wire_pll.reference_hz
        self.wire_pll.initialize_reference(time,self.next_wire_reference)
        self.wire_pll.set_reference(self.reference,time)
        self.wire_phase_target=None
        return PLLSerializer(self.channel,time,self.wire_pll)

    def clocks_ready(self):
        return super().clocks_ready() and self.wire_pll is not None and self.wire_pll.locked

    def schedule_wire(self,count,start,ppm=0):
        if ppm!=self.wire_reference_ppm:raise ValueError('Payload rate must match configured wired reference')
        if self.wire_pll is None or not self.wire_pll.locked:
            raise ValueError('Wired PLL is not qualified')
        # Predict the first integer oscillator phase at or after the requested
        # start without advancing any shared analog state into the future.
        candidate=copy.copy(self.wire_pll);candidate.advance(start)
        target=math.ceil(candidate.output_phase_cycles)
        deadline=self.wire_pll.edge_time(target)
        super().schedule_wire(count,start,ppm)
        self.wire_phase_target=target
        self.next_wire=deadline if count else math.inf

    def next_wire_deadline(self,deadline):
        self.wire_phase_target+=10
        return self.wire_pll.edge_time(self.wire_phase_target)

    def advance(self,time):
        # A timed mode command can create/restart the reference schedule. Merge
        # it here rather than discovering newly due reference ticks in the past.
        while min(self.next_wire_reference,self.command_events[0][0] if self.command_events else math.inf)<=time:
            tick=min(self.next_wire_reference,self.command_events[0][0] if self.command_events else math.inf)
            super().advance(tick)
            if self.wire_pll is not None:self.wire_pll.advance(tick)
            if self.next_wire_reference==tick:
                was_locked=self.wire_pll.locked
                qualified=self.wire_pll.observe_lock()
                self.wire_lock_history.append((tick,self.wire_pll.error,self.wire_pll.frequency_hz,qualified))
                if was_locked and not qualified and self.state=='active':
                    self.quiesce(tick,'wired TX clock lock loss')
                self.wire_ref_index+=1
                self.next_wire_reference=self.wire_ref_origin+self.wire_ref_index/self.wire_pll.reference_hz
                # The RF/sample-clock loop may already have qualified at this tick.
                super().advance(tick)
        super().advance(time)
        if self.wire_pll is not None:self.wire_pll.advance(time)

    def set_reference(self,present,time):
        super().set_reference(present,time)
        if self.wire_pll is not None:self.wire_pll.set_reference(present,time)

    def disturb_wire_tx(self,time,phase_cycles=0.,frequency_hz=0.):
        if self.wire_pll is None:raise ValueError('No configured wired oscillator')
        # Validate on a private state before moving the chip or changing clocks.
        candidate=copy.copy(self.wire_pll)
        candidate.disturb(time,phase_cycles,frequency_hz)
        self.advance(time)
        self.wire_pll.disturb(time,phase_cycles,frequency_hz)
        try:
            if self.wire_remaining:
                self.next_wire=self.wire_pll.edge_time(self.wire_phase_target)
                if self.next_wire<=time:raise ValueError('Word edge would replay')
            if self.serializer.active:
                self.serializer.retime()
                if self.serializer.deadline<=time:raise ValueError('Bit edge would replay')
        except ValueError:
            self.quiesce(time,'wired TX phase discontinuity')
            return False
        return True
