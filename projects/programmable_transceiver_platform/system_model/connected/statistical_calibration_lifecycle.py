"""Opt-in fixed-window ADC observation; deterministic validity stays separate."""
from calibration_statistics import assess_samples
from calibration_adc_lifecycle import AutomaticCalibrationChip

class StatisticalCalibrationMixin:
    def __init__(self,calibration_statistics=None,**kwargs):
        self.statistics_policy=None if calibration_statistics is None else dict(calibration_statistics)
        if self.statistics_policy is not None:
            allowed={'planned_samples','confidence','noise_sigma_v','systematic_bound_v',
                     'gain_interval','assumptions_validated'}
            if set(self.statistics_policy)-allowed:raise ValueError('Unknown statistical calibration option')
            # Exercise complete validation without making a validity claim.
            n=self.statistics_policy.get('planned_samples')
            if type(n) is not int or not 1<=n<=4096:raise ValueError('Require 1..4096 observations')
            assess_samples([0.]*n,tolerance_v=.001,**self.statistics_policy)
        self.statistics_samples=[];self.statistics_generation=None
        self.statistics_clip_start=0
        super().__init__(**kwargs)
    def execute_management(self,operation,payload,time):
        result=super().execute_management(operation,payload,time)
        if operation=='cal_status' and self.statistics_policy is not None:
            assessment=self.cal.result or {}
            # Bit 9 retains hard-bound validity. Bit 12 remains asserted until
            # deterministic accuracy is verified, even after statistical success.
            result['value']|=int(assessment.get('statistical_pass',False))<<13
            result['value']|=int(assessment.get('accuracy')=='statistical_failure')<<14
            if not self.cal.valid:result['value']|=1<<12
        if operation=='cal_start':
            self.statistics_samples=[];self.statistics_generation=self.cal.generation
            self.statistics_clip_start=self.adc_diagnostics['clipped_samples']
        return result
    def _drop_observation(self):
        super()._drop_observation()
        if self.cal.state!='done':
            self.statistics_samples=[];self.statistics_generation=None
    def _observe_maintenance(self,generation,epoch,value):
        if self.statistics_policy is None:
            return super()._observe_maintenance(generation,epoch,value)
        if generation!=self.cal.generation or generation!=self.statistics_generation or epoch!=self.epoch:
            raise ValueError('Stale statistical observation')
        if self.cal.state!='observe':raise ValueError('Statistical observation not ready')
        if not self.quiet():
            self.cal.cancel(self.time,'quiet ownership lost');return
        self.statistics_samples.append(value)
        if len(self.statistics_samples)<self.statistics_policy['planned_samples']:return
        result=assess_samples(self.statistics_samples,**self.statistics_policy,
            tolerance_v=self.cal.tolerance,quiet=self.quiet(),epoch=self.epoch,
            observation_epoch=epoch,range_limited=self.cal.range_limited,
            clipped=self.adc_diagnostics['clipped_samples']!=self.statistics_clip_start)
        result.update(done=True,range_limited=self.cal.range_limited)
        self.cal.result=result;self.cal.time=self.time;self.cal.state='done';self.cal.valid=False

class StatisticalCalibrationChip(StatisticalCalibrationMixin,AutomaticCalibrationChip):
    pass
