"""Integer-channel RF retargeting without erasing analog clock state."""
import math
from pulse_chip import PulseChip

class TunablePulseChip(PulseChip):
    def configure_rf_carrier(self,frequency_hz):
        if self.session.armed or self.state!='reset':raise ValueError('Pulse carrier tuning requires reset/disarmed state')
        if not isinstance(frequency_hz,int) or not 2300000000<=frequency_hz<=2500000000 or frequency_hz%40000000:
            raise ValueError('Pulse tuning currently requires an integer40MHz channel in2.3–2.5GHz')
        p=self.rf_pll;p.advance(self.time)
        old_current=p.current
        p.divider=frequency_hz//40000000;p.rate=p.reference_hz*p.divider
        # Reset digital divider/PFD state at the preserved oscillator phase.
        p.feedback_target=(math.floor(p.phase/p.divider)+1)*p.divider
        p.up=p.down=False;p.good=0;p.locked=False;p.first_lock=None
        if old_current!=p.current:p.transitions.append((p.time,p.current))
        self.rf_target_hz=frequency_hz
        self.install_segment(p.frequency_hz-self.rf_carrier,check=False)
