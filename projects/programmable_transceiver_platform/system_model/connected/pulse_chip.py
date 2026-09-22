"""Common-chip candidate with pulse-driven wired and RF integer-N synthesizers.

Tuning is intentionally rejected until feedback-edge retargeting is implemented.
This is an integration candidate, not the default qualified architecture.
"""
from programmable_chip import ProgrammableChip
from pulse_clock_service import PulseClockService

class PulseChip(ProgrammableChip):
    WIRE_PLL_CLASS=PulseClockService
    RF_PLL_CLASS=PulseClockService
    def envelope_phase(self,pll):
        # Pulse phase is continuous and unwrapped. A wrapped detector error must
        # never be substituted for oscillator phase when driving the mixers.
        return pll.output_phase_cycles-self.rf_carrier*pll.time
    def configure_rf_carrier(self,frequency_hz):
        raise ValueError('Pulse-clock carrier retargeting is not implemented')
