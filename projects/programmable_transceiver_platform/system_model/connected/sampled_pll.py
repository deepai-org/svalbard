"""Reference-sampled phase detector with held error driving a continuous PI/VCO.

This models finite comparison cadence, not charge-pump pulse shapes or dead zones.
Predictions carry their own immutable/scalar detector state and consume no events
from the real oscillator.
"""
import math
from autonomous_pll import AutonomousPLL


class SampledPLL(AutonomousPLL):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        self.initialize_reference(0.,1/self.reference_hz)

    def initialize_reference(self,time,first_tick):
        if time!=self.time or not math.isfinite(first_tick) or first_tick<=time:
            raise ValueError('Detector schedule requires a future reference edge at current time')
        self.detector_error=max(-.5,min(.5,self.error))
        self.detector_origin=first_tick-1/self.reference_hz
        self.detector_index=1;self.next_detector=first_tick
        self.detector_updates=0

    def control(self,error=None,integral=None):
        if not self.present:return self.hold_voltage
        i=self.integral if integral is None else integral
        return self.clip(self.kp*self.detector_error+i)

    def derivative(self,error,integral,time=None):
        if time is None:time=self.time
        raw=self.kp*self.detector_error+integral
        control=self.control(error,integral)
        frequency=self.free_hz+self.kvco*control+self.supply_shift_hz+self.rail_frequency(time)+self.frequency_noise.frequency(time)
        if frequency<=0:raise ValueError('Disturbance reverses oscillator phase')
        di=(self.ki*self.detector_error+self.antiwindup_rate*(control-raw)) if self.present else 0.
        return self.reference_hz-frequency/self.divider,di

    def advance(self,time):
        if not math.isfinite(time) or time<self.time:raise ValueError('Invalid sampled PLL time')
        while self.next_detector<=time:
            tick=self.next_detector
            super().advance(tick)
            if self.present:
                self.detector_error=max(-.5,min(.5,self.error));self.detector_updates+=1
            self.detector_index+=1
            self.next_detector=self.detector_origin+self.detector_index/self.reference_hz
        super().advance(time)
