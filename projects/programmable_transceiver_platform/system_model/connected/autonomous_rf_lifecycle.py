"""One autonomous RF synthesizer drives both mixers, independently of wired PLL.

RF envelopes use linear phase segments whose endpoints follow the nonlinear PLL.
Each segment uses the existing exact constant-frequency filter propagation; step
refinement bounds the approximation to curved oscillator phase inside a segment.
"""
import copy
import math
from autonomous_pll import AutonomousPLL
from autonomous_wire_lifecycle import AutonomousWireChip


class AutonomousRFChip(AutonomousWireChip):
    RF_PLL_CLASS=AutonomousPLL
    def __init__(self,rf_free_offset=-.04,rf_step_s=25e-9,**kwargs):
        if not math.isfinite(rf_step_s) or rf_step_s<=0:
            raise ValueError('RF phase integration step must be finite and positive')
        if not math.isfinite(rf_free_offset) or 2.4e9*(1+rf_free_offset)<=200e6:
            raise ValueError('RF VCO must remain positive over its tuning range')
        super().__init__(**kwargs)
        self.rf_carrier=2.4e9;self.rf_target_hz=2.4e9;self.rf_step=rf_step_s
        self.rf_pll=self.RF_PLL_CLASS(reference_hz=40e6*(1+self.wire_reference_ppm*1e-6),
            divider=60.,free_hz=self.rf_carrier*(1+rf_free_offset))
        self.rf_tx_phase=self.rf_rx_phase=0.
        self.rf_reference_index=1;self.next_rf_reference=1/self.rf_pll.reference_hz
        self.rf_lock_history=[];self.rf_segments=0;self.rf_continuity_error=0.
        self.install_segment(self.rf_pll.frequency_hz-self.rf_carrier,check=False)

    def configure_rf_carrier(self,frequency_hz):
        """Retarget average feedback ratio; retain the fixed 2.4GHz envelope frame.

        Divider rephasing preserves detector state and continuous oscillator phase.
        Fractional ratios are ideal averages here, not fractional-N edge synthesis.
        Loop gains, free-running frequency, filter state and noise are unchanged.
        """
        if self.session.armed or self.state!='reset':
            raise ValueError('RF carrier configuration requires reset/disarmed state')
        if not isinstance(frequency_hz,int) or not 2300000000<=frequency_hz<=2500000000:
            raise ValueError('RF carrier target outside candidate 2.3–2.5GHz range')
        p=self.rf_pll
        p.advance(self.time)
        phase=p.output_phase_cycles
        p.divider=frequency_hz/40e6
        p.phase_offset=phase-p.divider*(p.reference_hz*p.time-p.error)
        p.good=0;p.locked=False
        self.rf_target_hz=frequency_hz
        self.install_segment(p.frequency_hz-self.rf_carrier,check=False)

    def envelope_phase(self,pll):
        # Avoid subtracting two large carrier phase accumulators near lock.
        return (pll.reference_hz*pll.divider-self.rf_carrier)*pll.time-pll.divider*pll.error+pll.phase_offset

    def install_segment(self,frequency,check=True):
        phase=2*math.pi*self.envelope_phase(self.rf_pll)
        if check:
            old=2*math.pi*self.tx.rx_lo_hz*self.time+self.tx.rx_lo_phase
            difference=math.remainder(old-phase-self.rf_rx_phase,2*math.pi)
            self.rf_continuity_error=max(self.rf_continuity_error,abs(difference))
        self.tx.tx_lo_hz=self.tx.rx_lo_hz=frequency
        offset=phase-2*math.pi*frequency*self.time
        self.tx.tx_lo_phase=offset+self.rf_tx_phase
        self.tx.rx_lo_phase=offset+self.rf_rx_phase

    def make_serializer(self,time):
        self.rf_pll.advance(time)
        self.rf_pll.good=0;self.rf_pll.locked=False
        return super().make_serializer(time)

    def clocks_ready(self):
        return super().clocks_ready() and self.rf_pll.locked

    def schedule_lo(self,events):
        if list(events):raise ValueError('RF oscillator owns LO timing; use oscillator disturbances')
        return super().schedule_lo([])

    def configure_lo(self,tx_offset_hz=0.,rx_offset_hz=0.,tx_phase_rad=0.,rx_phase_rad=0.):
        tx_hz,rx_hz,tx_phase,rx_phase=tx_offset_hz,rx_offset_hz,tx_phase_rad,rx_phase_rad
        if self.session.armed or tx_hz!=0 or rx_hz!=0 or not all(math.isfinite(v) for v in (tx_phase,rx_phase)):
            raise ValueError('Shared autonomous LO permits disarmed branch phase settings only')
        self.rf_tx_phase=tx_phase;self.rf_rx_phase=rx_phase
        self.install_segment(self.rf_pll.frequency_hz-self.rf_carrier,check=False)

    def advance(self,time):
        if not math.isfinite(time) or time<self.time:raise ValueError('Invalid RF chip time')
        while self.time<time:
            end=min(time,self.time+self.rf_step,self.next_rf_reference,self.next_wire_reference,self.next_return,
                    self.command_events[0][0] if self.command_events else math.inf)
            if end>self.time:
                predicted=copy.copy(self.rf_pll);predicted.advance(end)
                frequency=(self.envelope_phase(predicted)-self.envelope_phase(self.rf_pll))/(end-self.time)
                self.install_segment(frequency)
                self.rf_segments+=1
            super().advance(end)
            self.rf_pll.advance(end)
            if self.next_rf_reference==end:
                was_locked=self.rf_pll.locked
                qualified=self.rf_pll.observe_lock()
                self.rf_lock_history.append((end,self.rf_pll.error,self.rf_pll.frequency_hz,qualified))
                self.rf_reference_index+=1
                self.next_rf_reference=self.rf_reference_index/self.rf_pll.reference_hz
                if was_locked and not qualified and self.state=='active':
                    self.quiesce(end,'RF oscillator lock loss')
                super().advance(end)
        super().advance(time)

    def set_reference(self,present,time):
        super().set_reference(present,time)
        self.rf_pll.set_reference(present,time)
        self.install_segment(self.rf_pll.frequency_hz-self.rf_carrier,check=False)

    def disturb_rf_lo(self,time,phase_cycles=0.,frequency_hz=0.):
        candidate=copy.copy(self.rf_pll)
        candidate.disturb(time,phase_cycles,frequency_hz)
        self.advance(time)
        before=self.tx.received
        self.rf_pll.disturb(time,phase_cycles,frequency_hz)
        self.install_segment(self.rf_pll.frequency_hz-self.rf_carrier,check=False)
        assert self.tx.received==before
