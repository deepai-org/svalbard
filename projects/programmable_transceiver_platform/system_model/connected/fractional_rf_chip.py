"""Pulse RF candidate with second-order integer feedback and300kHz candidate loop design."""
import copy,math
from fractions import Fraction
from pulse_chip import PulseChip
from pulse_clock_service import PulseClockService
from shaped_fractional_pll import SecondOrderSequence

class ShapedRFClock(PulseClockService):
    SEQUENCE_CLASS=SecondOrderSequence
    def __init__(self,**kwargs):
        kwargs.setdefault('bandwidth_hz',300e3)
        super().__init__(**kwargs)
        self.sequence=self.SEQUENCE_CLASS(Fraction(str(self.divider)))
        self.feedback_target=float(self.sequence.step())
    def observe_lock(self):
        first=self.first_lock
        super().observe_lock()
        # Eight comparisons can qualify a transient quiet patch. Cover at least
        # two complete second-order divider patterns and4us at40MHz instead.
        required=max(160,4*self.sequence.ratio.denominator)
        self.locked=self.good>=required
        self.first_lock=first if first is not None else (self.time if self.locked else None)
        return self.locked
    def feedback_interval(self):return self.sequence.step()
    def __copy__(self):
        clone=super().__copy__();clone.sequence=copy.copy(self.sequence);return clone
    def retarget(self,time,target_hz):
        ratio=Fraction(target_hz,40000000);sequence=self.SEQUENCE_CLASS(ratio)
        self.advance(time)
        # Restart on an integer VCO edge in the periodic sequence, without a
        # fractional edge or change to analog oscillator phase/filter charge.
        period_cycles=2*ratio.numerator
        target=math.floor(self.phase/period_cycles)*period_cycles
        while target<=self.phase:target+=sequence.step()
        old=self.current;self.sequence=sequence;self.feedback_target=target
        self.divider=float(ratio);self.rate=self.reference_hz*self.divider
        self.up=self.down=False;self.good=0;self.locked=False;self.first_lock=None
        if old!=self.current:self.transitions.append((time,self.current))

class FractionalRFChip(PulseChip):
    RF_PLL_CLASS=ShapedRFClock
    RF_CLOCK_CLASS=ShapedRFClock
    def __init__(self,rf_pulse_bandwidth_hz=300e3,rf_fast_fraction=.5,**kwargs):
        self.RF_PLL_CLASS=lambda **clock_kwargs:self.RF_CLOCK_CLASS(bandwidth_hz=rf_pulse_bandwidth_hz,fast_fraction=rf_fast_fraction,**clock_kwargs)
        super().__init__(**kwargs)
    def configure_rf_carrier(self,frequency_hz):
        if self.session.armed or self.state!='reset':raise ValueError('Fractional tuning requires reset/disarmed state')
        if not isinstance(frequency_hz,int) or not 2300000000<=frequency_hz<=2500000000 or frequency_hz%1000000:
            raise ValueError('Candidate carrier grid is1MHz within2.3–2.5GHz')
        self.rf_pll.retarget(self.time,frequency_hz)
        self.rf_target_hz=frequency_hz
        self.install_segment(self.rf_pll.frequency_hz-self.rf_carrier,check=False)
