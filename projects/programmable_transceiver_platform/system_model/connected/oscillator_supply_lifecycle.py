"""Actual host-switching rail impulses drive continuous autonomous VCO pulling."""
import copy
import math
from autonomous_rf_lifecycle import AutonomousRFChip


class OscillatorSupplyChip(AutonomousRFChip):
    def __init__(self,rf_hz_per_v=0.,wire_hz_per_v=0.,**kwargs):
        if not all(math.isfinite(v) for v in (rf_hz_per_v,wire_hz_per_v)):
            raise ValueError('Nonfinite oscillator supply sensitivity')
        self.rf_hz_per_v=rf_hz_per_v;self.wire_hz_per_v=wire_hz_per_v
        self.oscillator_supply_events=0;self.maximum_rf_pull=0.;self.maximum_wire_pull=0.
        super().__init__(**kwargs)

    def make_serializer(self,time):
        serializer=super().make_serializer(time)
        self.supply.advance(time)
        self.wire_pll.set_supply(time,self.supply.delta,self.supply.r*self.supply.c,self.wire_hz_per_v)
        return serializer

    def supply_impulse(self,time,delta_v):
        super().supply_impulse(time,delta_v)
        if not delta_v or not (self.rf_hz_per_v or self.wire_hz_per_v):return
        assert self.supply.time==time
        states=[]
        for pll,sensitivity in ((self.rf_pll,self.rf_hz_per_v),(self.wire_pll,self.wire_hz_per_v)):
            if pll is None:continue
            candidate=copy.copy(pll)
            candidate.set_supply(time,self.supply.delta,self.supply.r*self.supply.c,sensitivity)
            states.append((pll,candidate))
        # Commit both responses together, after advancing under the old rail.
        for pll,candidate in states:pll.__dict__.update(candidate.__dict__)
        self.oscillator_supply_events+=1
        self.maximum_rf_pull=max(self.maximum_rf_pull,abs(self.rf_pll.rail_frequency(time)))
        if self.wire_pll is not None:
            self.maximum_wire_pull=max(self.maximum_wire_pull,abs(self.wire_pll.rail_frequency(time)))
            if self.wire_remaining:self.next_wire=self.wire_pll.edge_time(self.wire_phase_target)
            if self.serializer.active:self.serializer.retime()
        # The frequency changes at this event; oscillator phase and filter output
        # do not. RF advance splits at every return-bus switching deadline.
        self.install_segment(self.rf_pll.frequency_hz-self.rf_carrier)

    def reference_metrics(self):
        r=super().reference_metrics()
        r['oscillator_supply']=dict(events=self.oscillator_supply_events,rf_hz_per_v=self.rf_hz_per_v,
            wire_hz_per_v=self.wire_hz_per_v,maximum_rf_pull_hz=self.maximum_rf_pull,
            maximum_wire_pull_hz=self.maximum_wire_pull)
        return r
