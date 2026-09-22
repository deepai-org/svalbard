"""Assumed probe-driver supply load coupled into the existing shared RC rail.

Supply current = enabled bias + positive output current + sink overhead fraction
of negative output current. Sinking never credits charge back into the supply.
A bounded left-endpoint charge approximation is refined by the screen.
"""
import math
from receiver_detect_resource_adapter import ResourceDetectChip

class SupplyDetectChip(ResourceDetectChip):
    def __init__(self,probe_load_scale=1.,probe_bias_a=100e-6,probe_sink_overhead=.1,probe_step_s=.5e-9,probe_gain_per_v=0.,probe_sensor_v_per_v=0.,**kwargs):
        if not all(math.isfinite(x) and x>=0 for x in (probe_load_scale,probe_bias_a,probe_sink_overhead)) or not math.isfinite(probe_step_s) or probe_step_s<=0:
            raise ValueError('Invalid probe driver load')
        if not all(math.isfinite(x) for x in (probe_gain_per_v,probe_sensor_v_per_v)):
            raise ValueError('Nonfinite probe supply sensitivity')
        self.probe_gain_per_v=probe_gain_per_v;self.probe_sensor_v_per_v=probe_sensor_v_per_v
        self.probe_minimum_gain=1.;self.probe_maximum_sensor_error=0.
        self.probe_load_scale=probe_load_scale;self.probe_bias_a=probe_bias_a
        self.probe_sink_overhead=probe_sink_overhead;self.probe_step=probe_step_s
        self.probe_supply_charge=0.;self.probe_supply_peak=0.;self.probe_load_steps=0
        super().__init__(**kwargs)
        self.probe.sensor=self.probe_sensor
    def probe_sensor(self,value):
        # Invoked at baseline/observation time after the chip reaches that time.
        self.supply.advance(self.time)
        offset=self.probe_sensor_v_per_v*self.supply.delta
        self.probe_maximum_sensor_error=max(self.probe_maximum_sensor_error,abs(offset))
        return value+offset
    def probe_supply_current(self):
        if self.probe.drive is None:return 0.
        currents=[(self.probe.drive*self.probe.drive_gain-leg.x[0])/leg.p['rs'] for leg in self.probe.legs]
        return self.probe_load_scale*(self.probe_bias_a+sum(max(i,0.)+self.probe_sink_overhead*max(-i,0.) for i in currents))
    def advance(self,time):
        if not math.isfinite(time) or time<self.time:raise ValueError('Invalid time')
        while self.time<time:
            self.probe.advance(self.time)
            end=min(time,self.probe.next_event,self.command_events[0][0] if self.command_events else math.inf)
            if self.probe.drive is not None:end=min(end,self.time+self.probe_step)
            self.supply.advance(self.time)
            gain=1+self.probe_gain_per_v*self.supply.delta
            if self.probe.drive is not None:
                if gain<=0:raise ValueError('Probe stimulus outside positive-gain envelope')
                self.probe.drive_gain=gain
                self.probe_minimum_gain=min(self.probe_minimum_gain,gain)
            current=self.probe_supply_current();charge=current*(end-self.time)
            if charge:
                self.supply.draw(self.time,charge)
                self.supply_impulse(self.time,-charge/self.supply.c)
                self.probe_supply_charge+=charge;self.probe_supply_peak=max(self.probe_supply_peak,current);self.probe_load_steps+=1
            super().advance(end)
        super().advance(time)
